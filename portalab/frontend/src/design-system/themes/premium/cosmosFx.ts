/**
 * issue 130: the « Cosmos » looks drawn by the GPU — fragments of ``badgeFx`` (same frame: ``p`` in half heights
 * of the shape, ``d`` the distance to its edge, < 0 inside, ``ax`` its width over its height, ``t`` the time,
 * ``o`` the colour laid so far). The first eight dress a shape (avatar frames, level badges, notifications,
 * titles and badges); the last four play over the whole stage, timed by ``u_age`` (celebrations, level-ups).
 */

export const COSMOS_BADGE_EFFECTS = [
  "stellar",
  "orrery",
  "starmap",
  "comet",
  "ringworld",
  "pulsar",
  "totality",
  "meteor",
  // the second wave
  "solar",
  "lunar",
] as const;
export const COSMOS_STAGE_EFFECTS = [
  "meteorstorm",
  "bigbang",
  "hyperjump",
  "constellate",
  // issue 133: not the cosmos, but a stage of the same kind — the Upside Down's gate
  "rift",
] as const;
export type CosmosEffect = (typeof COSMOS_BADGE_EFFECTS)[number] | (typeof COSMOS_STAGE_EFFECTS)[number];

export const COSMOS_EFFECTS: Record<CosmosEffect, string> = {
  // a nebula: glowing gas, pink and teal, folded by slow currents, dark lanes of dust, young stars blazing
  // inside; wisps of it drifting round the shape
  stellar: `
  vec2 w = vec2(fbm(p * 1.3 + vec2(t * 0.08, 0.0)), fbm(p * 1.3 + vec2(3.7, -t * 0.06)));
  float gas = fbm(p * 1.6 + w * 1.8 + vec2(0.0, t * 0.05));
  float dust = smoothstep(0.55, 0.78, fbm(p * 3.2 - w * 1.2 + 7.0));
  vec3 col = mix(vec3(0.05, 0.02, 0.12), vec3(0.85, 0.22, 0.55), smoothstep(0.3, 0.8, gas));
  col = mix(col, vec3(0.2, 0.78, 0.86), smoothstep(0.55, 0.9, w.x) * 0.7);
  col = mix(col, vec3(1.0, 0.86, 0.76), smoothstep(0.72, 0.95, gas) * 0.6);
  col *= 1.0 - dust * 0.6;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    vec2 sp = vec2((hash(vec2(fi, 61.0)) - 0.5) * 1.6 * ax, (hash(vec2(fi, 62.0)) - 0.5) * 1.5);
    float tw = 0.6 + 0.4 * sin(t * (1.5 + fi * 0.4) + fi * 2.0);
    vec2 g = abs(p - sp);
    float star = exp(-length(g) * 26.0) + exp(-g.x * 90.0) * exp(-g.y * 9.0) * 0.5 + exp(-g.y * 90.0) * exp(-g.x * 9.0) * 0.5;
    col += vec3(1.0, 0.92, 0.98) * star * tw;
  }
  col += vec3(0.95, 0.5, 1.0) * smoothstep(-0.25, 0.0, d) * 0.45;
  float wisp = fbm(p * 1.8 + w * 1.4 + vec2(t * 0.12, -t * 0.05)) * exp(-max(d, 0.0) * 2.4) * step(0.0, d);
  vec3 haze = mix(vec3(0.9, 0.3, 0.65), vec3(0.3, 0.8, 0.9), smoothstep(0.4, 0.7, w.y));
  o = over(o, haze, smoothstep(0.25, 0.65, wisp) * 0.7);
  o = over(o, col, smoothstep(0.03, -0.03, d));
`,
  // an orrery: a little sun in the middle, planets each on its own orbit — two inside the shape, two going
  // round it — lit on the side facing the sun, a faint line tracing every orbit
  orrery: `
  vec2 e = vec2(p.x / max(ax, 0.001), p.y);
  vec3 sky = mix(vec3(0.02, 0.03, 0.09), vec3(0.06, 0.05, 0.16), smoothstep(1.2, 0.0, length(e)));
  vec2 sg = p * 11.0;
  sky += vec3(0.9) * step(0.95, hash(floor(sg))) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + hash(floor(sg)) * 30.0));
  float sun = length(e);
  sky += vec3(1.0, 0.75, 0.3) * exp(-sun * 7.0) * (0.9 + 0.1 * sin(t * 3.0));
  sky += vec3(1.0, 0.95, 0.8) * smoothstep(0.13, 0.1, sun);
  sky += vec3(0.6, 0.7, 1.0) * smoothstep(-0.2, 0.0, d) * 0.35;
  o = over(o, vec3(1.0, 0.75, 0.35), exp(-max(d, 0.0) * 4.0) * 0.25 * step(0.0, d));
  o = over(o, sky, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float rad = 0.42 + 0.3 * fi + (fi > 1.5 ? 0.18 : 0.0);
    vec2 orbit = vec2(rad * max(ax, 1.0) * (fi > 1.5 ? 1.0 : 0.85), rad);
    float ring = abs(length(p / orbit) - 1.0) * rad;
    o = over(o, vec3(0.55, 0.65, 0.95), smoothstep(0.018, 0.0, ring) * 0.3);
    float a = t * (0.9 - 0.18 * fi) + fi * 1.7;
    vec2 at = vec2(cos(a), sin(a)) * orbit;
    float size = 0.07 + 0.035 * mod(fi * 3.0, 4.0) * 0.5;
    float dp = length(p - at);
    vec3 hue = fi < 0.5 ? vec3(0.85, 0.55, 0.35) : fi < 1.5 ? vec3(0.35, 0.6, 1.0) : fi < 2.5 ? vec3(0.95, 0.4, 0.3) : vec3(0.9, 0.78, 0.55);
    float lit = 0.35 + 0.65 * smoothstep(-0.6, 0.8, dot(normalize(-at), normalize(p - at + 1e-4)));
    o = over(o, hue * lit, smoothstep(size, size * 0.8, dp));
    o = over(o, hue, exp(-max(dp - size, 0.0) * 30.0) * 0.25);
  }
`,
  // a star chart: deep blue with the curved lines of its grid, a constellation drawn star after star and
  // line after line, then shining, then fading to start again; stars glinting round the shape
  starmap: `
  vec3 chart = mix(vec3(0.02, 0.05, 0.16), vec3(0.04, 0.1, 0.26), smoothstep(-1.0, 1.0, p.y));
  float gx = abs(fract((p.x + 0.05 * p.y * p.y) * 2.0) - 0.5);
  float gy = abs(fract(p.y * 2.0 + 0.04 * p.x * p.x) - 0.5);
  chart += vec3(0.25, 0.45, 0.85) * (smoothstep(0.03, 0.0, gx) + smoothstep(0.03, 0.0, gy)) * 0.18;
  vec2 sg = p * 13.0;
  chart += vec3(0.8, 0.88, 1.0) * step(0.93, hash(floor(sg))) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * 0.6;
  float cyc = mod(t, 9.0);
  float shine = exp(-abs(cyc - 6.0) * 2.0);
  float fade = smoothstep(9.0, 7.8, cyc);
  float lines = 0.0;
  float stars = 0.0;
  vec2 prev = vec2(0.0);
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    // the Plough's seven stars, fitted to the shape
    vec2 s = fi < 0.5 ? vec2(-0.95, 0.35) : fi < 1.5 ? vec2(-0.55, 0.42) : fi < 2.5 ? vec2(-0.2, 0.28) : fi < 3.5 ? vec2(0.12, 0.12)
      : fi < 4.5 ? vec2(0.2, -0.38) : fi < 5.5 ? vec2(0.82, -0.3) : vec2(0.78, 0.2);
    s *= vec2(min(ax, 1.6), 1.0) * 0.82;
    float born = fi * 0.55;
    float on = smoothstep(born, born + 0.3, cyc) * fade;
    stars += exp(-length(p - s) * 30.0) * on * (1.0 + shine);
    if (i > 0) {
      vec2 ab = s - prev;
      float h = clamp(dot(p - prev, ab) / dot(ab, ab), 0.0, 1.0);
      float drawn = clamp((cyc - born + 0.55) / 0.55, 0.0, 1.0);
      float seg = smoothstep(0.022, 0.0, length(p - prev - ab * h)) * step(h, drawn);
      lines += seg * fade;
    }
    if (i == 6) {
      vec2 ab = vec2(0.12, 0.12) * vec2(min(ax, 1.6), 1.0) * 0.82 - s;
      float h = clamp(dot(p - s, ab) / dot(ab, ab), 0.0, 1.0);
      lines += smoothstep(0.022, 0.0, length(p - s - ab * h)) * smoothstep(3.6, 4.0, cyc) * fade;
    }
    prev = s;
  }
  chart += vec3(0.55, 0.8, 1.0) * lines * (0.55 + 0.45 * shine);
  chart += vec3(1.0, 0.97, 0.88) * stars;
  chart += vec3(0.4, 0.65, 1.0) * smoothstep(-0.2, 0.0, d) * 0.45;
  float ang = atan(p.y, p.x / max(ax, 0.001));
  float glint = pow(0.5 + 0.5 * sin(ang * 5.0 + t * 0.7), 18.0) * exp(-max(d, 0.0) * 6.0) * step(0.0, d);
  o = over(o, vec3(0.6, 0.8, 1.0), exp(-max(d, 0.0) * 4.0) * 0.22 * step(0.0, d) + glint * 0.6);
  o = over(o, chart, smoothstep(0.03, -0.03, d));
`,
  // a comet: its icy head going round the shape, the dust tail curving behind it along its path, the blue
  // ion tail streaming straight away; inside, a frozen nucleus glittering
  comet: `
  vec2 e = vec2(p.x / max(ax, 0.001), p.y);
  float ang = atan(e.y, e.x);
  float head = t * 0.9;
  vec2 hp = vec2(cos(head), sin(head));
  vec2 hpos = hp * vec2(max(ax, 0.001), 1.0) * 1.22;
  float lag = mod(head - ang, 6.2832);
  float band = abs(length(e) - 1.22);
  float dust = exp(-band * mix(14.0, 5.0, clamp(lag / 1.8, 0.0, 1.0))) * smoothstep(1.9, 0.0, lag) * step(0.0, d);
  o = over(o, vec3(1.0, 0.86, 0.62), dust * 0.75);
  vec2 away = normalize(hp);
  vec2 rel = p - hpos;
  float along = dot(rel, away);
  float across = abs(dot(rel, vec2(-away.y, away.x)));
  float ion = smoothstep(0.03 + along * 0.08, 0.0, across) * smoothstep(0.0, 0.05, along) * exp(-along * 1.6);
  o = over(o, vec3(0.45, 0.7, 1.0), ion * 0.8 * step(0.0, d));
  float hd = length(rel);
  o = over(o, vec3(0.75, 0.92, 1.0), exp(-hd * 9.0) * 0.8);
  o = over(o, vec3(1.0), smoothstep(0.06, 0.03, hd));
  vec3 core = mix(vec3(0.04, 0.08, 0.18), vec3(0.2, 0.42, 0.62), fbm(p * 2.5 + vec2(t * 0.1, 0.0)));
  vec2 cg = p * 9.0;
  float ch = hash(floor(cg));
  core += vec3(0.85, 0.95, 1.0) * step(0.9, ch) * smoothstep(0.25, 0.0, length(fract(cg) - 0.5)) * (0.4 + 0.6 * sin(t * 3.0 + ch * 40.0));
  core += vec3(0.6, 0.85, 1.0) * smoothstep(-0.25, 0.0, d) * 0.5;
  o = over(o, core, smoothstep(0.03, -0.03, d));
`,
  // a ringed planet: banded clouds turning, a storm in them, the night side dark; its ring tilted across,
  // passing in front below and hidden behind above, its shadow on the planet
  ringworld: `
  vec2 e = vec2(p.x / max(ax, 0.001), p.y);
  float tilt = -0.32;
  vec2 q = mat2(cos(tilt), -sin(tilt), sin(tilt), cos(tilt)) * p;
  float lat = q.y + 0.06 * sin(q.x * 3.0 + t * 0.6);
  float bands = sin(lat * 13.0 + fbm(vec2(q.x * 1.5 - t * 0.25, lat * 4.0)) * 2.5);
  vec3 planet = mix(vec3(0.75, 0.55, 0.32), vec3(0.98, 0.88, 0.66), 0.5 + 0.5 * bands);
  planet = mix(planet, vec3(0.62, 0.38, 0.22), smoothstep(0.6, 0.9, fbm(vec2(q.x * 3.0 - t * 0.4, lat * 9.0))) * 0.5);
  vec2 spot = (q - vec2(0.25 * max(ax, 1.0) * sin(t * 0.25), -0.32)) * vec2(1.0, 1.8);
  planet = mix(planet, vec3(0.85, 0.35, 0.22), smoothstep(0.16, 0.08, length(spot)) * 0.8);
  float light = smoothstep(-1.1, 0.6, dot(normalize(vec2(-0.6, 0.5)), e)) * 0.85 + 0.15;
  planet *= light * (1.0 - 0.45 * smoothstep(-0.35, 0.0, d));
  vec2 rq = vec2(q.x / max(ax, 0.001), q.y * 4.2);
  float rr = length(rq);
  float ring = smoothstep(1.12, 1.16, rr) * smoothstep(1.75, 1.7, rr);
  ring *= 0.55 + 0.45 * sin(rr * 40.0) * sin(rr * 13.0 + 1.0);
  ring *= 1.0 - smoothstep(1.43, 1.46, rr) * smoothstep(1.5, 1.47, rr) * 0.9;
  vec3 rcol = mix(vec3(0.8, 0.72, 0.6), vec3(1.0, 0.95, 0.85), smoothstep(1.2, 1.7, rr));
  float front = step(q.y, 0.0);
  float inside = smoothstep(0.03, -0.03, d);
  float shadow = smoothstep(0.02, 0.0, abs(q.y - 0.12 - q.x * 0.05)) * 0.0;
  o = over(o, vec3(0.95, 0.75, 0.45), exp(-max(d, 0.0) * 3.5) * 0.25 * step(0.0, d));
  o = over(o, rcol * 0.85, ring * (1.0 - front) * (1.0 - inside));
  o = over(o, planet * (1.0 - shadow), inside);
  o = over(o, rcol, ring * front);
`,
  // a pulsar: a dazzling core spinning, two beams sweeping round like a lighthouse, a pulse ringing out at
  // each turn, the lines of its magnetic field arching inside
  pulsar: `
  vec2 e = vec2(p.x / max(ax, 0.001), p.y);
  float r = length(e);
  float spin = t * 2.2;
  vec2 dir = vec2(cos(spin), sin(spin));
  float across = abs(dot(e, vec2(-dir.y, dir.x)));
  float beam = exp(-across * mix(18.0, 5.0, clamp(r / 3.0, 0.0, 1.0))) * smoothstep(0.05, 0.4, r);
  float pulse = fract(t * 2.2 / 3.1416);
  float wave = smoothstep(0.05, 0.0, abs(r - pulse * 2.6)) * (1.0 - pulse);
  vec3 body = mix(vec3(0.03, 0.02, 0.1), vec3(0.15, 0.08, 0.35), smoothstep(1.0, 0.0, r));
  float field = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float k = 0.35 + 0.25 * fi;
    vec2 m = mat2(cos(spin * 0.5), -sin(spin * 0.5), sin(spin * 0.5), cos(spin * 0.5)) * e;
    float dip = abs(length(vec2(abs(m.x) - k, m.y)) - k);
    field += smoothstep(0.03, 0.0, dip) * (0.5 - fi * 0.12);
  }
  body += vec3(0.55, 0.45, 1.0) * field * 0.6;
  body += vec3(0.75, 0.85, 1.0) * beam * 0.9;
  body += vec3(1.0) * exp(-r * 9.0) * (0.85 + 0.15 * sin(t * 30.0));
  body += vec3(0.6, 0.5, 1.0) * smoothstep(-0.2, 0.0, d) * 0.45;
  o = over(o, vec3(0.7, 0.8, 1.0), beam * step(0.0, d) * 0.85);
  o = over(o, vec3(0.65, 0.55, 1.0), wave * 0.7 * step(0.0, d));
  o = over(o, vec3(0.5, 0.4, 1.0), exp(-max(d, 0.0) * 4.5) * 0.3 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // a total eclipse: the moon a black disc, the pearly corona streaming out round it, pink prominences on its
  // edge, and now and then the diamond ring flashing
  totality: `
  float ang = atan(p.y, p.x / max(ax, 0.001));
  float r = max(d, 0.0);
  float streak = fbm(vec2(ang * 3.2, r * 1.5 - t * 0.08)) * 0.7 + 0.3 * noise(vec2(ang * 11.0, t * 0.2));
  float corona = exp(-r * (2.2 + 4.0 * (1.0 - streak))) * step(0.0, d);
  o = over(o, mix(vec3(0.75, 0.82, 1.0), vec3(1.0, 0.98, 0.94), exp(-r * 6.0)), corona * 0.85);
  float prom = smoothstep(0.62, 0.85, noise(vec2(ang * 7.0, t * 0.3))) * exp(-r * 22.0) * step(0.0, d);
  o = over(o, vec3(1.0, 0.35, 0.5), prom * 0.9);
  float cyc = mod(t, 8.0);
  float ring = exp(-abs(cyc - 7.0) * 3.0);
  float at = 2.3;
  vec2 rim = vec2(cos(at) * max(ax, 0.001), sin(at)) * 1.0;
  vec2 g = abs(p - rim);
  float diamond = (exp(-length(g) * 14.0) + exp(-g.x * 60.0) * exp(-g.y * 4.0) * 0.6 + exp(-g.y * 60.0) * exp(-g.x * 4.0) * 0.6) * ring;
  o = over(o, vec3(1.0, 0.98, 0.92), diamond);
  vec3 moon = vec3(0.015, 0.015, 0.03) + vec3(0.06, 0.07, 0.1) * fbm(p * 3.0) * 0.6;
  moon += vec3(0.85, 0.88, 1.0) * smoothstep(-0.06, 0.0, d) * 0.8;
  o = over(o, moon, smoothstep(0.03, -0.03, d));
`,
  // a meteor shower: a night sky inside, shooting stars streaking across and beyond the shape, each with its
  // fading trail and a flare as it burns
  meteor: `
  vec3 sky = mix(vec3(0.02, 0.02, 0.08), vec3(0.08, 0.06, 0.2), smoothstep(-1.0, 1.0, p.y));
  vec2 sg = p * 12.0;
  float sh = hash(floor(sg));
  sky += vec3(0.9, 0.92, 1.0) * step(0.93, sh) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.5 + sh * 40.0));
  sky += vec3(0.5, 0.45, 1.0) * smoothstep(-0.2, 0.0, d) * 0.4;
  o = over(o, vec3(0.5, 0.45, 1.0), exp(-max(d, 0.0) * 4.5) * 0.22 * step(0.0, d));
  o = over(o, sky, smoothstep(0.03, -0.03, d));
  vec2 way = normalize(vec2(-1.0, -0.55));
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float period = 2.3 + fi * 0.7;
    float k = floor((t + fi * 1.3) / period);
    float life = fract((t + fi * 1.3) / period) * 1.6;
    vec2 from = vec2((0.2 + hash(vec2(k, fi + 71.0)) * 1.2) * max(ax, 1.0), 0.6 + hash(vec2(k, fi + 72.0)) * 0.9);
    vec2 head = from + way * life * (2.4 + ax);
    vec2 rel = p - head;
    float along = dot(rel, -way);
    float across = abs(dot(rel, vec2(-way.y, way.x)));
    float trail = smoothstep(0.03, 0.0, across) * smoothstep(0.9, 0.0, along) * step(0.0, along);
    float burn = smoothstep(0.0, 0.2, life) * smoothstep(1.6, 1.1, life);
    o = over(o, mix(vec3(0.6, 0.75, 1.0), vec3(1.0, 0.95, 0.85), smoothstep(0.4, 0.0, along)), trail * burn);
    o = over(o, vec3(1.0), exp(-length(rel) * 28.0) * burn);
  }
`,
  // the sun: its surface boiling inside, the corona streaming round the shape, prominences looping off it
  solar: `
  float ang = atan(p.y, p.x / max(ax, 0.001));
  float r = max(d, 0.0);
  float streams = fbm(vec2(ang * 4.0, r * 2.5 - t * 0.3));
  o = over(o, vec3(1.0, 0.55, 0.15), exp(-r * (2.4 + 2.0 * (1.0 - streams))) * step(0.0, d) * 0.75);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float a0 = hash(vec2(fi, 21.0)) * 6.2832 + t * 0.06 * (fi - 1.0);
    float da = mod(ang - a0 + 3.1416, 6.2832) - 3.1416;
    float x = da / (0.25 + 0.2 * hash(vec2(fi, 22.0)));
    float h = (0.25 + 0.3 * hash(vec2(fi, 23.0))) * (0.75 + 0.25 * sin(t * 0.6 + fi * 2.0));
    float arc = h * sqrt(max(0.0, 1.0 - x * x));
    float loop = smoothstep(0.07, 0.0, abs(r - arc)) * step(abs(x), 1.0) * step(0.0, d);
    o = over(o, mix(vec3(1.0, 0.3, 0.08), vec3(1.0, 0.75, 0.3), noise(vec2(ang * 20.0, t * 2.0))), loop * 0.85);
  }
  vec2 q = p * 2.4;
  float gran = fbm(q + vec2(fbm(q + t * 0.2), fbm(q - t * 0.15)) * 1.5);
  vec3 surf = mix(vec3(0.95, 0.42, 0.06), vec3(1.0, 0.88, 0.5), gran);
  surf += vec3(1.0, 0.95, 0.8) * smoothstep(-0.25, 0.0, d) * 0.45;
  o = over(o, surf, smoothstep(0.03, -0.03, d));
`,
  // the moon: grey seas and craters, the line between day and night sweeping across with its phases, a
  // silver halo and a few stars round it
  lunar: `
  vec2 e = vec2(p.x / max(ax, 1.0), p.y);
  float phase = sin(t * 0.35);
  float seas = smoothstep(0.45, 0.65, fbm(p * 1.4 + 3.0));
  vec3 moon = mix(vec3(0.93, 0.92, 0.88), vec3(0.55, 0.57, 0.62), seas);
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    vec2 cc = (vec2(hash(vec2(fi, 11.0)), hash(vec2(fi, 12.0))) - 0.5) * vec2(1.5 * ax, 1.5);
    float cr = 0.12 + 0.14 * hash(vec2(fi, 13.0));
    float dc = length(p - cc);
    moon *= 1.0 - 0.15 * smoothstep(cr, cr * 0.6, dc) + 0.08 * smoothstep(0.04, 0.0, abs(dc - cr));
  }
  moon *= 0.85 + 0.15 * fbm(p * 6.0);
  float lit = smoothstep(-0.12, 0.12, e.x * sign(phase) + (1.0 - abs(phase)) * 1.1 - 0.15);
  moon = mix(moon * 0.12 + vec3(0.02, 0.03, 0.06), moon, lit);
  moon += vec3(0.8, 0.85, 1.0) * smoothstep(-0.2, 0.0, d) * 0.3;
  o = over(o, vec3(0.75, 0.82, 1.0), exp(-max(d, 0.0) * 3.5) * 0.35 * step(0.0, d));
  vec2 sg = p * 7.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(1.0), step(0.93, sh) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * step(0.15, d) * (0.5 + 0.5 * sin(t * 2.0 + sh * 30.0)));
  o = over(o, moon, smoothstep(0.03, -0.03, d));
`,
  // a meteor storm over the whole screen: from a radiant high up, dozens of shooting stars streak out, a few
  // fireballs flaring green and gold, over a deep sky
  meteorstorm: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.5, 5.3, tl);
  o = over(o, vec3(0.01, 0.01, 0.05), 0.5 * fade);
  vec2 radiant = vec2(-0.3 * aspect, 0.55);
  o = over(o, vec3(0.5, 0.6, 1.0), exp(-length(c - radiant) * 6.0) * 0.25 * fade);
  for (int i = 0; i < 64; i++) {
    float fi = float(i);
    float start = hash(vec2(fi, 101.0)) * 4.8;
    float life = (tl - start) / (0.5 + 0.6 * hash(vec2(fi, 102.0)));
    if (life < 0.0 || life > 1.4) continue;
    float a = -0.2 - hash(vec2(fi, 103.0)) * 2.4;
    vec2 way = vec2(cos(a), sin(a));
    vec2 from = radiant + way * (0.05 + 0.35 * hash(vec2(fi, 104.0)));
    vec2 head = from + way * life * (1.0 + 1.0 * hash(vec2(fi, 105.0)));
    vec2 rel = c - head;
    float along = dot(rel, -way);
    float across = abs(dot(rel, vec2(-way.y, way.x)));
    float big = step(0.85, hash(vec2(fi, 106.0)));
    float width = mix(0.0022, 0.0055, big) * (1.0 + along * 1.5);
    float trail = smoothstep(width, 0.0, across) * smoothstep(0.45 + big * 0.3, 0.0, along) * step(0.0, along);
    float burn = smoothstep(0.0, 0.12, life) * smoothstep(1.4, 0.85, life);
    vec3 col = mix(vec3(0.75, 0.85, 1.0), mix(vec3(0.5, 1.0, 0.6), vec3(1.0, 0.82, 0.45), hash(vec2(fi, 107.0))), big);
    o = over(o, col, trail * burn * fade);
    o = over(o, vec3(1.0), exp(-length(rel) * mix(200.0, 70.0, big)) * burn * fade);
    o = over(o, col, big * exp(-length(rel) * 8.0) * burn * 0.35 * fade);
  }
  vec2 sg = c * 40.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(1.0), step(0.986, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(tl * 4.0 + sh * 30.0)) * 0.8 * fade);
`,
  // the big bang: a point of light, a blinding flash, a ball of fire swelling and cooling from white to
  // orange to violet, the cosmic web forming in it, then little galaxies spinning away
  bigbang: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c);
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(6.6, 5.4, tl);
  float point = smoothstep(0.0, 0.5, tl) * step(tl, 0.8);
  o = over(o, vec3(1.0), exp(-r * mix(120.0, 40.0, point)) * point);
  float bang = max(tl - 0.8, 0.0);
  float after = step(0.8, tl);
  float flash = exp(-bang * 6.0) * after;
  float size = 1.5 * (1.0 - exp(-bang * 1.0)) + 0.001;
  float cool = clamp(bang / 3.2, 0.0, 1.0);
  float x = r / size;
  vec2 w = vec2(fbm(c * 3.0 + bang * 0.2), fbm(c * 3.0 + 5.0 - bang * 0.15));
  float churn = fbm(c * 5.0 + w * 1.5 - vec2(0.0, bang * 0.3));
  // the fireball: white-hot at its heart, orange towards its edge, cooling to violet — never opaque
  vec3 hot = mix(vec3(1.0, 0.97, 0.88), vec3(1.0, 0.6, 0.18), smoothstep(0.0, 0.9, x + cool * 0.6));
  hot = mix(hot, vec3(0.55, 0.2, 0.7), smoothstep(0.35, 1.0, cool));
  float ball = smoothstep(1.0, 0.55, x) * (0.35 + 0.65 * churn) * (0.85 - 0.6 * cool) * exp(-max(bang - 1.4, 0.0) * 1.3) * after;
  o = over(o, hot, ball * fade);
  float shell = exp(-abs(x - 1.0) * 14.0) * exp(-bang * 0.7) * after;
  o = over(o, vec3(1.0, 0.85, 0.65), shell * 0.8 * fade);
  // the cosmic web as it cools: thin bright filaments only
  // the cosmic web as it cools: thin threads where the matter gathers, brighter at their knots
  float level = fbm(c * 3.5 + w * 2.0);
  float thread = smoothstep(0.018, 0.0, abs(level - 0.5)) + 0.6 * smoothstep(0.012, 0.0, abs(fbm(c * 7.0 + w * 3.0) - 0.5));
  float knots = smoothstep(0.62, 0.8, fbm(c * 6.0 - w)) * thread;
  float filaments = thread * smoothstep(0.35, 0.9, cool);
  o = over(o, vec3(0.65, 0.72, 1.0), filaments * 0.55 * fade);
  o = over(o, vec3(1.0, 0.9, 0.8), knots * smoothstep(0.35, 0.9, cool) * 0.6 * fade);
  o = over(o, vec3(1.0, 0.98, 0.95), flash * exp(-r * 1.2));
  for (int i = 0; i < 16; i++) {
    float fi = float(i);
    float a = hash(vec2(fi, 111.0)) * 6.2832;
    vec2 at = vec2(cos(a), sin(a)) * (0.15 + 0.75 * hash(vec2(fi, 112.0))) * (1.0 - exp(-bang * 0.6));
    vec2 g = c - at;
    float gr = length(g) + 0.0001;
    float arms = sin(atan(g.y, g.x) * 2.0 - log(gr) * 3.0 + tl * 2.0 + fi);
    float gal = exp(-gr * 70.0) + smoothstep(0.04, 0.0, gr) * (0.5 + 0.5 * arms) * 0.6;
    vec3 gc = mix(vec3(0.8, 0.6, 1.0), vec3(1.0, 0.85, 0.65), hash(vec2(fi, 113.0)));
    o = over(o, gc, gal * smoothstep(1.6, 2.6, tl) * fade);
  }
`,
  // a jump through hyperspace: the stars begin to slide outwards, stretch into long streaks as the ship
  // speeds up, a tunnel of blue light rushes past — a flash — and it comes out before a nebula in bloom
  hyperjump: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c) + 1e-4;
  float a = atan(c.y, c.x);
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.3, tl) * smoothstep(6.6, 5.4, tl);
  float speed = smoothstep(0.4, 2.5, tl) * (1.0 - smoothstep(2.65, 2.85, tl));
  float travel = 0.25 * tl + 2.2 * max(tl - 0.6, 0.0) * max(tl - 0.6, 0.0) * step(tl, 2.8);
  o = over(o, vec3(0.0, 0.01, 0.04), 0.55 * fade * step(tl, 2.8));
  // the stars, in rings of directions, sliding out along their rays; streaks as the speed grows
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 g = vec2(a / 6.2832 * (70.0 + fk * 50.0), log(r) * 5.0 - travel * (5.0 + fk * 2.0));
    vec2 id = floor(g);
    vec2 f = fract(g);
    float on = step(0.8, hash(id + fk * 13.0));
    float len = 0.04 + speed * 0.95;
    float lane = smoothstep(0.1, 0.0, abs(f.x - 0.5 - (hash(id + 3.0) - 0.5) * 0.6));
    float streak = lane * smoothstep(0.0, 0.03, f.y) * smoothstep(len, len * 0.3, f.y);
    vec3 sc = mix(vec3(0.85, 0.9, 1.0), vec3(0.45, 0.65, 1.0), speed * hash(id + 5.0));
    o = over(o, sc, on * streak * smoothstep(0.02, 0.15, r) * fade * step(tl, 2.85));
  }
  // the tunnel: rings of blue light rushing outwards, a glow at its far end
  float rings = pow(0.5 + 0.5 * sin(log(r) * 18.0 - tl * 26.0), 6.0) * smoothstep(0.05, 0.6, r);
  o = over(o, vec3(0.35, 0.55, 1.0), rings * speed * 0.2 * fade);
  o = over(o, vec3(0.75, 0.85, 1.0), exp(-r * 6.0) * speed * 0.8 * fade);
  float flash = exp(-abs(tl - 2.75) * 9.0);
  o = over(o, vec3(0.9, 0.95, 1.0), flash);
  // out of the jump: a nebula blooms in front, the stars still again
  float there = smoothstep(2.75, 3.6, tl) * fade;
  vec2 q = c * (1.4 - 0.25 * smoothstep(2.75, 6.0, tl));
  vec2 w = vec2(fbm(q * 2.0 + vec2(tl * 0.05, 0.0)), fbm(q * 2.0 + vec2(4.0, -tl * 0.04)));
  float gas = fbm(q * 2.5 + w * 2.0);
  float body = smoothstep(0.75, 0.1, length(q * vec2(0.8, 1.0)) + (gas - 0.5) * 0.7);
  vec3 neb = mix(vec3(0.5, 0.12, 0.65), vec3(1.0, 0.25, 0.55), smoothstep(0.4, 0.72, gas));
  neb = mix(neb, vec3(0.2, 0.85, 0.95), smoothstep(0.5, 0.85, w.x) * 0.7);
  neb = mix(neb, vec3(1.0, 0.92, 0.88), smoothstep(0.7, 0.95, gas) * 0.6);
  float lit = clamp((fbm(q * 2.5 + w * 2.0 - normalize(q + 1e-4) * 0.05) - gas) * 12.0 + 0.5, 0.0, 1.0);
  neb *= 0.8 + 0.6 * lit;
  float fil = 1.0 - abs(2.0 * fbm(q * 5.0 + w * 3.0) - 1.0);
  neb += vec3(1.0, 0.7, 0.9) * pow(fil, 8.0) * 0.5;
  o = over(o, neb, clamp(body * (0.55 + 0.45 * gas), 0.0, 0.95) * there);
  o = over(o, vec3(0.9, 0.95, 1.0), exp(-length(q) * 18.0) * there);
  vec2 sg = c * 38.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(1.0), step(0.985, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.6 + 0.4 * sin(tl * 3.0 + sh * 30.0)) * there);
`,
  // a constellation is born round your new level: stars light up one by one on a circle, lines join them
  // into a crown of stars, it flashes, sparkles drift; the sky turns slowly behind
  constellate: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / min(u_res.x, u_res.y);
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.4, tl) * smoothstep(6.6, 5.6, tl);
  float turn = tl * 0.03;
  vec2 rc = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * c;
  vec2 sg = rc * 34.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(0.02, 0.03, 0.1), 0.4 * fade);
  o = over(o, vec3(0.85, 0.9, 1.0), step(0.982, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(tl * 3.0 + sh * 40.0)) * fade);
  float lines = 0.0;
  float stars = 0.0;
  float done = smoothstep(3.6, 3.9, tl);
  for (int i = 0; i < 10; i++) {
    float fi = float(i);
    float a = fi / 10.0 * 6.2832 + 1.5708;
    float rad = mod(fi, 2.0) < 0.5 ? 0.42 : 0.3;
    vec2 s = vec2(cos(a), sin(a)) * rad;
    float a2 = (fi + 1.0) / 10.0 * 6.2832 + 1.5708;
    float rad2 = mod(fi + 1.0, 2.0) < 0.5 ? 0.42 : 0.3;
    vec2 s2 = vec2(cos(a2), sin(a2)) * rad2;
    float born = 0.3 + fi * 0.3;
    stars += exp(-length(c - s) * 70.0) * smoothstep(born, born + 0.2, tl) * (1.0 + 2.0 * exp(-abs(tl - born - 0.1) * 8.0));
    vec2 ab = s2 - s;
    float h = clamp(dot(c - s, ab) / dot(ab, ab), 0.0, 1.0);
    float drawn = clamp((tl - born - 0.15) / 0.3, 0.0, 1.0);
    lines += smoothstep(0.004, 0.0, length(c - s - ab * h)) * step(h, drawn);
  }
  float flash = exp(-abs(tl - 3.9) * 5.0);
  o = over(o, vec3(0.6, 0.8, 1.0), exp(-abs(length(c) - 0.36) * 30.0) * flash * 0.5 * fade);
  o = over(o, vec3(0.55, 0.78, 1.0), lines * (0.7 + 0.3 * done) * fade);
  o = over(o, vec3(1.0, 0.95, 0.85), clamp(stars, 0.0, 1.0) * fade);
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    float life = fract(tl * (0.2 + 0.15 * hash(vec2(fi, 131.0))) + hash(vec2(fi, 132.0)));
    float a = hash(vec2(fi, 133.0)) * 6.2832;
    vec2 pos = vec2(cos(a), sin(a)) * (0.36 + life * 0.4);
    o = over(o, vec3(1.0, 0.9, 0.7), smoothstep(0.006, 0.0, length(c - pos)) * (1.0 - life) * done * fade);
  }
`,
  // issue 133, the Upside Down's gate: the room goes dark and the lights flicker, a red crack tears down the
  // middle and opens, its lips burning, its membrane pulsing, sticky strands across it; we are drawn in
  // (everything grows from the middle until the rift fills the screen), a red shudder — and we stand in the
  // Upside Down: blue-grey fog, ash drifting up, vines over the edges, red lightning in the clouds overhead
  rift: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.3, tl) * smoothstep(6.6, 5.4, tl);
  float enter = smoothstep(2.55, 3.05, tl);
  // the room: dark, the lights flickering before it tears
  float flick = step(0.4, hash(vec2(floor(tl * 13.0), 7.0))) * (1.0 - smoothstep(0.6, 1.4, tl));
  o = over(o, vec3(0.02, 0.0, 0.01), (0.5 + 0.25 * flick) * fade * (1.0 - enter));
  // drawn in: the rift and all round it grow from the middle, faster and faster, with a tremor
  float push = exp(max(tl - 1.7, 0.0) * 2.4);
  float shake = smoothstep(0.5, 1.5, tl) * (1.0 - enter) * 0.004;
  vec2 q = (c + vec2(hash(vec2(floor(tl * 30.0), 3.0)) - 0.5, hash(vec2(floor(tl * 30.0), 4.0)) - 0.5) * shake) / push;
  // the tear: a jagged vertical slit, widest at its middle, opening over a second
  float open = smoothstep(0.35, 1.8, tl);
  float jag = (fbm(vec2(q.y * 6.0, 3.0)) - 0.5) * 0.12 + (fbm(vec2(q.y * 24.0, 9.0)) - 0.5) * 0.035;
  float len = 0.06 + 0.5 * open;
  float along = clamp(1.0 - abs(q.y) / len, 0.0, 1.0);
  float width = 0.08 * open * pow(along, 0.65);
  float dx = abs(q.x - jag * (0.4 + open)) - width;
  float rim = step(abs(q.y), len);
  float inside = smoothstep(0.004, -0.004, dx) * rim;
  // the other side: fog, the red glow of the sky, lightning, vines and ash
  vec2 w = c * 1.3 + vec2(0.0, tl * 0.03);
  float fog = fbm(w * 2.0 + vec2(tl * 0.06, -tl * 0.02));
  vec3 world = mix(vec3(0.03, 0.05, 0.09), vec3(0.2, 0.24, 0.32), fog);
  world += vec3(0.6, 0.06, 0.05) * 0.45 * smoothstep(0.0, 0.5, c.y) * (0.7 + 0.3 * sin(tl * 1.7));
  float strike = step(0.55, hash(vec2(floor(tl * 2.5), 21.0))) * exp(-fract(tl * 2.5) * 7.0);
  float bolt = smoothstep(0.02, 0.0, abs(c.x - 0.3 * sin(floor(tl * 2.5) * 5.1) - (fbm(vec2(c.y * 9.0, floor(tl * 2.5))) - 0.5) * 0.25)) * smoothstep(-0.05, 0.3, c.y);
  world += vec3(1.0, 0.2, 0.15) * strike * (bolt * 1.2 + fbm(c * 3.0 + 11.0) * smoothstep(0.0, 0.5, c.y) * 0.8);
  float edge = max(abs(c.x) / (0.5 * aspect), abs(c.y) / 0.5);
  float vine = smoothstep(0.04, 0.0, abs(fbm(c * 4.5 + 3.0) - 0.5)) + 0.6 * smoothstep(0.025, 0.0, abs(fbm(c * 9.0 + 8.0) - 0.5));
  world = mix(world, vec3(0.1, 0.03, 0.03), clamp(vine, 0.0, 1.0) * smoothstep(0.5, 1.0, edge) * 0.9);
  for (int i = 0; i < 48; i++) {
    float fi = float(i);
    float rise = 0.025 + 0.05 * hash(vec2(fi, 141.0));
    vec2 pos = vec2((hash(vec2(fi, 142.0)) - 0.5) * aspect + sin(tl * 0.6 + fi) * 0.03, fract(hash(vec2(fi, 143.0)) + tl * rise) - 0.5);
    float size = 0.002 + 0.005 * hash(vec2(fi, 144.0));
    world = mix(world, vec3(0.85, 0.85, 0.9), smoothstep(size, 0.0, length(c - pos)) * 0.8);
  }
  o = over(o, world, max(inside, enter) * fade);
  // strands of membrane across the opening, torn away as it widens
  float strand = smoothstep(0.1, 0.0, abs(fract(q.y * 8.0 + fbm(q * 5.0) * 2.0) - 0.5)) * inside * (1.0 - smoothstep(0.9, 2.1, tl));
  o = over(o, vec3(0.45, 0.1, 0.08), strand * 0.65 * fade);
  // its lips: white-hot right at the edge, burning red outside it, veins pulsing in the membrane round it
  float pulse = 0.75 + 0.25 * sin(tl * 7.0);
  float gap = max(dx, 0.0);
  float edge0 = abs(dx);
  float lips = (1.0 - enter) * fade * exp(-max(abs(q.y) - len, 0.0) * 30.0);
  float outside = smoothstep(-0.004, 0.004, dx);
  o = over(o, vec3(0.7, 0.06, 0.04), exp(-gap * 7.0) * 0.4 * open * lips * outside);
  float veins = smoothstep(0.035, 0.0, abs(fbm(q * 9.0 + vec2(0.0, tl * 0.15)) - 0.5)) * exp(-gap * 9.0) * (0.3 + along);
  o = over(o, vec3(0.65, 0.05, 0.07), veins * 0.8 * open * pulse * lips * outside);
  o = over(o, vec3(1.0, 0.25, 0.08), exp(-edge0 * 90.0) * pulse * (0.4 + 0.6 * open) * lips);
  o = over(o, vec3(1.0, 0.82, 0.55), exp(-edge0 * 400.0) * (0.5 + 0.5 * open) * lips);
  // red light spilling out of it onto the inside of the opening
  o = over(o, vec3(0.9, 0.15, 0.08), exp(-edge0 * 25.0) * 0.35 * inside * lips);
  // the crossing: a red shudder
  o = over(o, vec3(0.75, 0.08, 0.06), exp(-abs(tl - 2.85) * 10.0) * 0.45 * fade);
`,
};
