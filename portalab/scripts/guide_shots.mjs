/**
 * Issue 239: the member guide's screenshots, taken from a running portal and annotated — each element framed,
 * numbered, and when it says so a bubble with an arrow pointing at it. The shots are described in a JSON file
 * (``docs/member-guide/shots/<page>.json``, one per page): the page, the screen, what is done first, the part
 * kept and the marks. A shot may name the API paths a page reads by POST (``"reads": ["/api/v1/search"]``);
 * every other write is refused.
 * The interface is shown in the guide's language and the default palette whatever the account's; nothing is
 * changed on the portal.
 * By default only the content is kept (``main``), never the header nor the member's own panel.
 *
 *     node scripts/guide_shots.mjs docs/member-guide/shots --base https://127.0.0.1:8443 --login admin \
 *         --password-file <file> --out <folder> [--language fr] [--only name,name] [--names <file>]
 *
 * ``"picker": true`` keeps « Who's there? » on screen (the shot of the picker itself).
 * A bubble's words or a selector naming a label may be given in each language: ``{"en": "…", "fr": "…"}``.
 * A step may replace names in the picture (``"replace": true``), after the page is drawn: the real names and
 * the ones shown are read from ``--names`` (a JSON map kept out of the repository, e.g.
 * ``deploy/secrets/shot_names.json``: ``{"Real": "Shown", "=R": "S"}`` — a key starting with ``=`` replaces
 * only a whole text, an initial; one starting with ``~`` blurs the element holding that word). Without the file, a shot asking for it is refused: real names never show.
 * The password is read from a file, never from the command line. Then ``wiki_import.py --shots <folder>``.
 */

import { mkdirSync, readdirSync, readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const here = dirname(fileURLToPath(import.meta.url));
const { chromium } = createRequire(join(here, "../frontend/package.json"))(
	"@playwright/test",
);

const { values, positionals } = parseArgs({
	allowPositionals: true,
	options: {
		base: { type: "string" },
		login: { type: "string" },
		"password-file": { type: "string" },
		out: { type: "string" },
		language: { type: "string", default: "fr" },
		only: { type: "string" },
		names: { type: "string" },
	},
});
if (
	!positionals[0] ||
	!values.base ||
	!values.login ||
	!values["password-file"] ||
	!values.out
) {
	console.error(
		"usage: guide_shots.mjs <shots.json | folder> --base … --login … --password-file … --out …",
	);
	process.exit(2);
}
const base = values.base.replace(/\/$/, "");
const password = readFileSync(values["password-file"], "utf8").trim();
// a file of shots, or a folder of them (one per page of the guide)
const source = positionals[0];
const files = statSync(source).isDirectory()
	? readdirSync(source)
			.filter((name) => name.endsWith(".json"))
			.sort()
			.map((name) => join(source, name))
	: [source];
// issue 457: a text in each language (``{"en": "…", "fr": "…"}``) — a bubble's words, a selector naming a
// label — is read in the shot's language
const localize = (value) => {
	if (Array.isArray(value)) return value.map(localize);
	if (value === null || typeof value !== "object") return value;
	const keys = Object.keys(value);
	if (keys.length && keys.every((key) => /^[a-z]{2}$/.test(key)))
		return value[values.language] ?? value.en ?? value[keys[0]];
	return Object.fromEntries(
		Object.entries(value).map(([key, item]) => [key, localize(item)]),
	);
};
const shots = files
	.flatMap((file) => JSON.parse(readFileSync(file, "utf8")))
	.map(localize);
const PRIVATE_CSS =
	".avatar-frame img, .shell-avatar-button img, .profile-hero__avatar img, .ds-avatar img, .shell-profile img, " +
	'.household-face img, img[src*="/avatar"], [data-shot-blur], ' +
	// a portal's own wiki pages (only Portalab's guide shows)
	'a[href^="/wiki/"]:not([href^="/wiki/guide-"]):not([href="/wiki/"]) { filter: blur(6px); }';
// issue 456: the real names to hide, never written in the repository
const names = values.names
	? JSON.parse(readFileSync(values.names, "utf8"))
	: null;
const only = values.only ? new Set(values.only.split(",")) : null;
const out = resolve(values.out);
mkdirSync(out, { recursive: true });

const SCREENS = {
	desktop: { viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 },
	phone: {
		viewport: { width: 400, height: 860 },
		deviceScaleFactor: 2,
		isMobile: true,
		hasTouch: true,
	},
};

/** The marks drawn over the page, in the screen's coordinates: a frame per element, its number, its bubble. */
function annotate({ marks, area }) {
	const COLOR = "#ff3d71";
	const layer = document.createElement("div");
	layer.id = "guide-shot-marks";
	layer.style.cssText =
		"position:fixed;inset:0;z-index:2147483647;pointer-events:none;font-family:Inter,system-ui,sans-serif";
	const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	svg.setAttribute("width", String(innerWidth));
	svg.setAttribute("height", String(innerHeight));
	svg.style.cssText = "position:absolute;inset:0";
	svg.innerHTML = `<defs><marker id="guide-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${COLOR}"/></marker></defs>`;
	layer.append(svg);
	document.body.append(layer); // in the page from the start: the bubbles are measured there
	const missing = [];
	marks.forEach((mark, index) => {
		const shown = [...document.querySelectorAll(mark.target)].filter((e) => {
			const r = e.getBoundingClientRect();
			return r.width > 2 && r.height > 2;
		});
		const found = mark.pick === "last" ? shown.at(-1) : shown[0];
		if (!found) {
			missing.push(mark.target);
			return;
		}
		const pad = mark.pad ?? 6;
		const r = found.getBoundingClientRect();
		const box = {
			x: Math.max(area.x + 2, r.left - pad),
			y: Math.max(area.y + 2, r.top - pad),
		};
		box.w = Math.min(area.x + area.width - 2, r.right + pad) - box.x;
		box.h = Math.min(area.y + area.height - 2, r.bottom + pad) - box.y;
		const frame = document.createElementNS(
			"http://www.w3.org/2000/svg",
			"rect",
		);
		for (const [k, v] of Object.entries({
			x: box.x,
			y: box.y,
			width: box.w,
			height: box.h,
			rx: 10,
		}))
			frame.setAttribute(k, String(v));
		frame.setAttribute("fill", "none");
		frame.setAttribute("stroke", COLOR);
		frame.setAttribute("stroke-width", "3");
		frame.style.filter =
			"drop-shadow(0 0 2px rgba(255,255,255,.9)) drop-shadow(0 2px 6px rgba(0,0,0,.45))";
		svg.append(frame);
		const number = mark.n ?? index + 1;
		const badge = document.createElement("span");
		badge.textContent = String(number);
		badge.style.cssText = `position:absolute;left:${box.x - 13}px;top:${box.y - 13}px;width:26px;height:26px;border-radius:50%;background:${COLOR};color:#fff;font:700 14px/26px Inter,system-ui,sans-serif;text-align:center;box-shadow:0 0 0 2px #fff,0 2px 6px rgba(0,0,0,.4)`;
		layer.append(badge);
		if (!mark.label) return;
		// the bubble beside the frame, on the side asked (or the roomiest), its arrow to the frame's edge
		const bubble = document.createElement("span");
		bubble.textContent = mark.label;
		bubble.style.cssText = `position:absolute;max-width:240px;padding:6px 11px;border-radius:9px;background:${COLOR};color:#fff;font:600 14px/1.3 Inter,system-ui,sans-serif;box-shadow:0 0 0 2px #fff,0 3px 10px rgba(0,0,0,.4)`;
		layer.append(bubble);
		// measured where nothing narrows it, then kept at that width wherever it goes
		bubble.style.boxSizing = "border-box";
		bubble.style.maxWidth = "none";
		bubble.style.whiteSpace = "nowrap";
		const line = Math.ceil(bubble.getBoundingClientRect().width) + 1;
		bubble.style.whiteSpace = "normal";
		bubble.style.width = `${Math.min(line, mark.width ?? 250)}px`;
		const bw = bubble.offsetWidth;
		const bh = bubble.offsetHeight;
		const room = {
			top: box.y - area.y,
			bottom: area.y + area.height - (box.y + box.h),
			left: box.x - area.x,
			right: area.x + area.width - (box.x + box.w),
		};
		const side =
			mark.side ?? Object.entries(room).sort((a, b) => b[1] - a[1])[0][0];
		const gap = mark.gap ?? 38;
		const cx = box.x + box.w / 2;
		const cy = box.y + box.h / 2;
		let bx;
		let by;
		let from;
		let to;
		if (side === "top" || side === "bottom") {
			bx = cx - bw / 2 + (mark.shift ?? 0);
			by = side === "top" ? box.y - gap - bh : box.y + box.h + gap;
			to = [cx, side === "top" ? box.y - 3 : box.y + box.h + 3];
		} else {
			bx = side === "left" ? box.x - gap - bw : box.x + box.w + gap;
			by = cy - bh / 2 + (mark.shift ?? 0);
			to = [side === "left" ? box.x - 3 : box.x + box.w + 3, cy];
		}
		bx = Math.min(Math.max(bx, area.x + 6), area.x + area.width - bw - 6);
		by = Math.min(Math.max(by, area.y + 6), area.y + area.height - bh - 6);
		bubble.style.left = `${bx}px`;
		bubble.style.top = `${by}px`;
		if (side === "top")
			from = [Math.min(Math.max(to[0], bx + 12), bx + bw - 12), by + bh];
		else if (side === "bottom")
			from = [Math.min(Math.max(to[0], bx + 12), bx + bw - 12), by];
		else if (side === "left")
			from = [bx + bw, Math.min(Math.max(to[1], by + 8), by + bh - 8)];
		else from = [bx, Math.min(Math.max(to[1], by + 8), by + bh - 8)];
		const arrow = document.createElementNS(
			"http://www.w3.org/2000/svg",
			"line",
		);
		for (const [k, v] of Object.entries({
			x1: from[0],
			y1: from[1],
			x2: to[0],
			y2: to[1],
		}))
			arrow.setAttribute(k, String(v));
		arrow.setAttribute("stroke", COLOR);
		arrow.setAttribute("stroke-width", "3");
		arrow.setAttribute("stroke-linecap", "round");
		arrow.setAttribute("marker-end", "url(#guide-arrow)");
		arrow.style.filter = "drop-shadow(0 0 1.5px rgba(255,255,255,.9))";
		svg.append(arrow);
	});
	return missing;
}

async function act(page, step) {
	if (step.goto)
		await page.goto(base + step.goto, {
			waitUntil: "domcontentloaded",
			timeout: 120000,
		});
	if (step.css) {
		// a picture's arrangement (a card shown larger), as a constructed sheet: the portal's policy refuses inline styles
		await page.evaluate((css) => {
			const sheet = new CSSStyleSheet();
			sheet.replaceSync(css);
			document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
		}, step.css);
	}
	if (step.click) await page.locator(step.click).first().click();
	// issue 456: names replaced in the picture (a real family's children never shown in public screenshots)
	if (step.replace) {
		if (!names)
			throw new Error("this shot replaces names: pass --names <file>");
		await page.evaluate((pairs) => {
			const walker = document.createTreeWalker(
				document.body,
				NodeFilter.SHOW_TEXT,
			);
			for (let node = walker.nextNode(); node; node = walker.nextNode()) {
				let text = node.nodeValue ?? "";
				for (const [from, to] of Object.entries(pairs))
					if (from.startsWith("~")) continue;
					else
						text = from.startsWith("=")
							? text.trim() === from.slice(1)
								? to
								: text
							: // a whole word only: « Alex » is not « Alexandre » (a key's edge that is a letter)
								text.replace(
									new RegExp(
										`${/^\p{L}/u.test(from) ? "(?<!\\p{L})" : ""}${from.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}${/\p{L}$/u.test(from) ? "(?!\\p{L})" : ""}`,
										"gu",
									),
									to,
								);
				if (text !== node.nodeValue) node.nodeValue = text;
			}
			// a key starting with « ~ »: the element holding that word is blurred (a private name, a brand)
			const hidden = Object.keys(pairs)
				.filter((key) => key.startsWith("~"))
				.map((key) => key.slice(1).toLowerCase());
			const all = document.createTreeWalker(
				document.body,
				NodeFilter.SHOW_TEXT,
			);
			for (let node = all.nextNode(); node; node = all.nextNode()) {
				const value = (node.nodeValue ?? "").toLowerCase();
				if (hidden.some((word) => value.includes(word)))
					node.parentElement?.setAttribute("data-shot-blur", "");
			}
			for (const element of document.querySelectorAll(
				"[title], [alt], [aria-label]",
			))
				for (const attribute of ["title", "alt", "aria-label"])
					if (
						hidden.some((word) =>
							(element.getAttribute(attribute) ?? "")
								.toLowerCase()
								.includes(word),
						)
					)
						element.setAttribute("data-shot-blur", "");
		}, names);
	}
	if (step.follow) {
		// a link's address, rewritten (a set's page → its work's page)
		let href = await page.locator(step.follow).first().getAttribute("href");
		for (const [from, to] of step.rewrite ?? []) href = href.replace(from, to);
		await page.goto(base + href, {
			waitUntil: "domcontentloaded",
			timeout: 120000,
		});
	}
	if (step.waitFor)
		await page.locator(step.waitFor).first().waitFor({ timeout: 60000 });
	if (step.scroll)
		await page
			.locator(step.scroll)
			.first()
			.evaluate((e) => e.scrollIntoView({ block: "center" }));
	await page.waitForTimeout(step.wait ?? 600);
}

const browser = await chromium.launch();
let failed = 0;

/** One shot: true when taken. */
async function take(shot, last) {
	const screen = SCREENS[shot.screen ?? "desktop"];
	const context = await browser.newContext({
		...screen,
		viewport: {
			...screen.viewport,
			height: shot.height ?? screen.viewport.height,
		},
		ignoreHTTPSErrors: true,
		reducedMotion: "reduce", // a still picture: nothing turning or swaying
	});
	await context.request.post(`${base}/api/v1/auth/login`, {
		data: { login: values.login, password },
		timeout: 120000,
	});
	const page = await context.newPage();
	// nothing is changed on the portal: what the page would write (a view, a mission, a setting) is refused —
	// but the reads a page makes by POST (a search: its query in the body), when the shot names them
	const reads = shot.reads ?? [];
	await page.route("**/api/v1/**", (route) => {
		const request = route.request();
		const path = new URL(request.url()).pathname;
		// issue 457: choosing the account's own profile on « Who's there? » only switches this browser's session
		const read =
			request.method() === "POST" &&
			(path === "/api/v1/household/switch" || reads.includes(path));
		return request.method() === "GET" || read
			? route.fallback()
			: route.fulfill({ status: 204, body: "" });
	});
	// issue 457: the portal's default colours, whatever palette the account chose — only in this browser
	await page.route("**/api/v1/me/preferences", async (route) => {
		if (route.request().method() !== "GET") return route.fallback();
		const response = await route.fetch();
		const body = await response.json();
		const preferences = (body.preferences ?? []).map((item) =>
			item.key === "ui.palette" ? { ...item, value: "theme" } : item,
		);
		await route.fulfill({ response, json: { ...body, preferences } });
	});
	// the guide's language, whatever the account's — only in this browser
	await page.route("**/api/v1/i18n/context", async (route) => {
		const response = await route.fetch();
		const body = await response.json();
		// dates and numbers too, as a member reading in that language sees them (not the account's region)
		const locale =
			body.language === values.language ? body.locale : values.language;
		await route.fulfill({
			response,
			json: { ...body, language: values.language, locale },
		});
	});
	try {
		await act(page, { goto: shot.route, wait: shot.settle ?? 4000 });
		// issue 457: an account with profiles is asked « Who's there? » first — its holder is chosen
		const picker = page.locator(
			".household-picker__grid li:first-child .household-tile",
		);
		if (!shot.picker && (await picker.count())) {
			await picker.first().click();
			await page.waitForTimeout(3000);
			await act(page, { goto: shot.route, wait: shot.settle ?? 4000 });
		}
		for (const step of shot.before ?? []) await act(page, step);
		if (names) {
			// issue 457: public screenshots — members' faces blurred, real names replaced, whatever the shot
			await act(page, { css: PRIVATE_CSS });
			await act(page, { replace: true });
		}
		const clip = await page
			.locator(shot.clip ?? "main")
			.first()
			.evaluate(
				(element, [extra, most]) => {
					const r = element.getBoundingClientRect();
					const [top, right, bottom, left] = extra;
					const x = Math.max(0, r.left - left);
					const y = Math.max(0, r.top - top);
					return {
						x,
						y,
						width: Math.min(innerWidth, r.right + right) - x,
						height:
							Math.min(
								innerHeight,
								r.bottom + bottom,
								y + (most ?? Number.POSITIVE_INFINITY),
							) - y,
					};
				},
				[shot.margin ?? [0, 0, 0, 0], shot.maxHeight],
			);
		const missing = await page.evaluate(annotate, {
			marks: shot.marks ?? [],
			area: clip,
		});
		if (missing.length)
			console.warn(`${shot.name}: not shown — ${missing.join(", ")}`);
		const file = join(out, `${shot.name}.jpg`);
		await page.screenshot({ path: file, clip, type: "jpeg", quality: 88 });
		console.log(
			`shot   ${shot.name} (${Math.round(clip.width)}×${Math.round(clip.height)})`,
		);
		return true;
	} catch (error) {
		if (last) {
			await page
				.screenshot({ path: join(out, `${shot.name}.failed.png`) })
				.catch(() => {});
			console.error(`failed ${shot.name}: ${error.message.split("\n")[0]}`);
		}
		return false;
	} finally {
		await context.close();
	}
}

for (const shot of shots) {
	if (only && !only.has(shot.name)) continue;
	// a page that loads slowly once (a portal just started) is given a second chance
	if (!(await take(shot, false)) && !(await take(shot, true))) failed += 1;
}
await browser.close();
process.exit(failed ? 1 : 0);
