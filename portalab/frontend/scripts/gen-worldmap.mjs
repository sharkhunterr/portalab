/**
 * 027 — world map for the media statistics (production countries): Natural Earth 110m country outlines
 * (world-atlas) projected once, equirectangularly, into SVG paths keyed by ISO 3166-1 alpha-2, with an
 * anchor point per country. Run `node scripts/gen-worldmap.mjs` after changing the projection; the output
 * is a static, lazily-loaded JSON — nothing to fetch at run time.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { feature } from "topojson-client";

const W = 1000;
const NORTH = 84;
const SOUTH = -58; // Antarctica left out
const H = Math.round((W * (NORTH - SOUTH)) / 360);
const x = (lon) => ((lon + 180) / 360) * W;
const y = (lat) => ((NORTH - lat) / (NORTH - SOUTH)) * H;
const r = (n) => Math.round(n * 10) / 10;

const NUMERIC = {
  "004": "AF",
  "008": "AL",
  "012": "DZ",
  "024": "AO",
  "032": "AR",
  "036": "AU",
  "040": "AT",
  "044": "BS",
  "048": "BH",
  "050": "BD",
  "051": "AM",
  "052": "BB",
  "056": "BE",
  "064": "BT",
  "068": "BO",
  "070": "BA",
  "072": "BW",
  "076": "BR",
  "084": "BZ",
  "090": "SB",
  "096": "BN",
  100: "BG",
  104: "MM",
  108: "BI",
  112: "BY",
  116: "KH",
  120: "CM",
  124: "CA",
  140: "CF",
  144: "LK",
  148: "TD",
  152: "CL",
  156: "CN",
  158: "TW",
  170: "CO",
  174: "KM",
  178: "CG",
  180: "CD",
  188: "CR",
  191: "HR",
  192: "CU",
  196: "CY",
  203: "CZ",
  204: "BJ",
  208: "DK",
  214: "DO",
  218: "EC",
  222: "SV",
  226: "GQ",
  231: "ET",
  232: "ER",
  233: "EE",
  242: "FJ",
  246: "FI",
  250: "FR",
  262: "DJ",
  266: "GA",
  268: "GE",
  270: "GM",
  275: "PS",
  276: "DE",
  288: "GH",
  300: "GR",
  316: "GU",
  320: "GT",
  324: "GN",
  328: "GY",
  332: "HT",
  336: "VA",
  340: "HN",
  344: "HK",
  348: "HU",
  352: "IS",
  356: "IN",
  360: "ID",
  364: "IR",
  368: "IQ",
  372: "IE",
  376: "IL",
  380: "IT",
  384: "CI",
  388: "JM",
  392: "JP",
  398: "KZ",
  400: "JO",
  404: "KE",
  408: "KP",
  410: "KR",
  414: "KW",
  417: "KG",
  418: "LA",
  422: "LB",
  426: "LS",
  428: "LV",
  430: "LR",
  434: "LY",
  440: "LT",
  442: "LU",
  450: "MG",
  454: "MW",
  458: "MY",
  466: "ML",
  478: "MR",
  484: "MX",
  496: "MN",
  498: "MD",
  499: "ME",
  504: "MA",
  508: "MZ",
  512: "OM",
  516: "NA",
  524: "NP",
  528: "NL",
  540: "NC",
  548: "VU",
  554: "NZ",
  558: "NI",
  562: "NE",
  566: "NG",
  578: "NO",
  586: "PK",
  591: "PA",
  598: "PG",
  600: "PY",
  604: "PE",
  608: "PH",
  616: "PL",
  620: "PT",
  624: "GW",
  626: "TL",
  630: "PR",
  634: "QA",
  642: "RO",
  643: "RU",
  646: "RW",
  682: "SA",
  686: "SN",
  688: "RS",
  694: "SL",
  702: "SG",
  703: "SK",
  704: "VN",
  705: "SI",
  706: "SO",
  710: "ZA",
  716: "ZW",
  724: "ES",
  728: "SS",
  729: "SD",
  740: "SR",
  748: "SZ",
  752: "SE",
  756: "CH",
  760: "SY",
  762: "TJ",
  764: "TH",
  768: "TG",
  780: "TT",
  788: "TN",
  792: "TR",
  795: "TM",
  800: "UG",
  804: "UA",
  807: "MK",
  818: "EG",
  826: "GB",
  834: "TZ",
  840: "US",
  854: "BF",
  858: "UY",
  860: "UZ",
  862: "VE",
  882: "WS",
  887: "YE",
  894: "ZM",
};

const topo = JSON.parse(
  readFileSync(new URL("../node_modules/world-atlas/countries-110m.json", import.meta.url)),
);
const world = feature(topo, topo.objects.countries);

function ringPath(ring) {
  let d = "";
  let previous = null;
  for (const [lon, lat] of ring) {
    if (lat < SOUTH - 1) continue;
    const point = [r(x(lon)), r(y(Math.min(NORTH, lat)))];
    if (previous && point[0] === previous[0] && point[1] === previous[1]) continue;
    d += `${previous ? "L" : "M"}${point[0]} ${point[1]}`;
    previous = point;
  }
  return previous ? `${d}Z` : "";
}

function area(ring) {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i += 1)
    sum += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  return Math.abs(sum / 2);
}

const countries = {};
let rest = "";
for (const shape of world.features) {
  const polygons =
    shape.geometry?.type === "Polygon" ? [shape.geometry.coordinates] : (shape.geometry?.coordinates ?? []);
  const d = polygons.map((polygon) => polygon.map(ringPath).join("")).join("");
  if (!d) continue;
  const code = NUMERIC[String(shape.id).padStart(3, "0")];
  if (!code) {
    rest += d;
    continue;
  }
  // anchor: the centre of the largest outer ring (its points' mean)
  const largest = polygons.map((p) => p[0]).sort((a, b) => area(b) - area(a))[0];
  const lon = largest.reduce((s, p) => s + p[0], 0) / largest.length;
  const lat = largest.reduce((s, p) => s + p[1], 0) / largest.length;
  countries[code] = { d, x: r(x(lon)), y: r(y(lat)), name: shape.properties?.name ?? code };
}
const out = new URL("../src/features/media/insights/world-map.json", import.meta.url);
writeFileSync(out, `${JSON.stringify({ w: W, h: H, countries, rest })}\n`);
console.log(
  `world map: ${Object.keys(countries).length} countries, ${Math.round(readFileSync(out).length / 1024)} KB`,
);
