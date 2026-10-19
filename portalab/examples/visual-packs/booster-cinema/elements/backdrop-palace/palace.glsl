// Cinema — the booster stage in a movie palace at night (a stage: gl_FragCoord, u_res, t; into o): the walls
  // dark red, the screen showing an old silvery film (24 frames a second: its flicker, its gate weave, its
  // scratches and dust), the velvet curtains drawn aside, swaying, their gold-fringed valance, the projector's
  // beam coming over the audience's heads with dust and smoke turning in it, the rows of seats in perspective lit
  // by the screen, heads in silhouette, art deco sconces. The camera breathes.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y + vec2(0.003 * sin(t * 0.3), 0.002 * sin(t * 0.23));
  float aa = 1.5 / u_res.y;
  float frame = floor(t * 24.0);
  float flick = 0.86 + 0.1 * hash(vec2(frame, 1.0)) + 0.04 * sin(t * 50.0);
  // the hall: dark red walls, gold pilasters, a sunburst over the screen
  vec3 wall = mix(vec3(0.07, 0.015, 0.02), vec3(0.16, 0.04, 0.04), smoothstep(-0.5, 0.4, c.y)) * (0.8 + 0.3 * fbm(c * vec2(8.0, 2.0)));
  o = over(o, wall, 1.0);
  float pil = smoothstep(0.012, 0.006, abs(abs(c.x) - 0.72)) * step(-0.25, c.y);
  o = over(o, vec3(0.55, 0.38, 0.14) * (0.6 + 0.4 * sin(c.y * 60.0)), pil * 0.7);
  vec2 sb = c - vec2(0.0, 0.47);
  float sa = atan(sb.y, sb.x);
  float burst = step(0.0, sb.y) * smoothstep(0.32, 0.28, length(sb)) * step(0.5, fract(sa / 3.1416 * 9.0)) * step(0.06, length(sb));
  o = over(o, vec3(0.6, 0.42, 0.16), burst * 0.45);
  // the screen: an old silvery film — clouds over a sea and a lighthouse, jumping in its gate, flickering,
  // scratched, a speck of dust now and then, its light falling off at the edges
  vec2 sq = c - vec2(0.0, 0.17);
  float onScreen = smoothstep(aa, -aa, max(abs(sq.x) - 0.4, abs(sq.y) - 0.205));
  vec2 weave = vec2(hash(vec2(frame, 2.0)) - 0.5, hash(vec2(frame, 3.0)) - 0.5) * 0.004;
  vec2 f = sq + weave;
  float sky = 0.55 + 0.35 * smoothstep(-0.2, 0.2, f.y) + 0.25 * (fbm(vec2(f.x * 4.0 - t * 0.05, f.y * 9.0)) - 0.5);
  float sea = step(f.y, -0.06);
  float wave = 0.3 + 0.18 * fbm(vec2(f.x * 14.0 + t * 0.25, (f.y + 0.06) * 70.0 - t * 0.6)) + 0.25 * pow(fbm(vec2(f.x * 30.0 - t * 0.4, f.y * 120.0)), 3.0) * smoothstep(-0.2, -0.06, f.y);
  float lum = mix(sky, wave, sea);
  vec2 lh = f - vec2(0.18, -0.06);
  float tower = step(abs(lh.x), 0.012 - lh.y * 0.04) * step(0.0, lh.y) * step(lh.y, 0.09);
  lum = mix(lum, 0.12, tower);
  float lamp = exp(-length(lh - vec2(0.0, 0.095)) * 60.0);
  float sweep = pow(max(cos(atan(lh.y - 0.095, lh.x) - sin(t * 0.8) * 1.4), 0.0), 40.0) * smoothstep(0.5, 0.0, length(lh));
  lum += lamp * 0.8 + sweep * 0.25;
  float scratch = step(0.997, hash(vec2(floor(f.x * 400.0), floor(frame / 3.0)))) * 0.22;
  float speck = step(0.6, noise(f * 60.0 + frame * 7.13)) * step(0.985, hash(vec2(frame, 9.0))) * 0.6;
  lum = (lum + scratch - speck) * flick * (0.75 + 0.25 * smoothstep(0.5, 0.0, length(sq * vec2(0.8, 1.6))));
  lum += (hash(gl_FragCoord.xy + frame) - 0.5) * 0.08;
  o = over(o, vec3(0.88, 0.9, 0.96) * clamp(lum, 0.0, 1.2), onScreen);
  // the screen's light on the hall
  vec3 glow = vec3(0.55, 0.6, 0.75) * flick;
  o = over(o, glow, exp(-length((c - vec2(0.0, 0.17)) * vec2(0.6, 1.2)) * 3.2) * 0.12 * (1.0 - onScreen));
  // the curtains drawn aside, deep folds swaying, lit by the screen on their inner edge; the valance and its fringe
  float sway = 0.006 * sin(t * 0.9 + c.y * 3.0);
  float cx = abs(c.x) - 0.4 - sway;
  float tie = 0.06 * smoothstep(0.1, -0.15, c.y) * smoothstep(-0.4, -0.15, c.y);
  float curtain = smoothstep(-0.004, 0.004, cx - tie) * step(abs(c.x), 0.68) * step(-0.36, c.y);
  float folds = 0.55 + 0.45 * sin(c.x * 140.0 + sin(c.y * 6.0 + t * 0.7) * 1.5);
  float rim = exp(-max(cx - tie, 0.0) * 40.0);
  vec3 velvet = vec3(0.42, 0.04, 0.06) * folds * (0.45 + 0.5 * rim * flick);
  o = over(o, velvet, curtain);
  float valY = 0.37 + 0.012 * abs(sin(c.x * 11.0 + 0.4));
  float valance = step(valY, c.y) * step(c.y, 0.45) * step(abs(c.x), 0.68);
  o = over(o, vec3(0.45, 0.05, 0.07) * (0.7 + 0.3 * sin(c.x * 50.0)) * (0.7 + 0.3 * flick), valance);
  float fringe = step(valY - 0.018, c.y) * step(c.y, valY) * step(0.45, fract(c.x * 180.0)) * step(abs(c.x), 0.68);
  o = over(o, vec3(0.85, 0.62, 0.22) * (0.6 + 0.4 * flick), fringe);
  // art deco sconces on the pilasters
  for (int k = 0; k < 2; k++) {
    vec2 lq = c - vec2(k == 0 ? -0.72 : 0.72, 0.22);
    float fan = step(0.0, lq.y) * smoothstep(0.045, 0.04, length(lq)) * step(0.5, fract(atan(lq.y, lq.x) / 3.1416 * 6.0 + 0.25));
    o = over(o, vec3(0.95, 0.75, 0.4), fan * 0.8);
    o = over(o, vec3(1.0, 0.65, 0.3), exp(-length(lq * vec2(1.0, 0.7)) * 9.0) * 0.3);
  }
  // the projector's beam, from the booth behind us to the screen: smoke turning in it, dust catching the light
  vec2 bo = vec2(0.03, 0.62);
  vec2 bd = c - bo;
  float along = clamp(-bd.y / 0.45, 0.0, 1.0);
  float width = mix(0.02, 0.42, along);
  float beam = smoothstep(width, width * 0.55, abs(bd.x - bd.y * 0.05)) * step(bd.y, 0.0) * smoothstep(0.0, 0.08, along) * step(0.17, c.y + 0.21);
  float smoke = fbm(vec2(c.x * 5.0 + t * 0.05, c.y * 3.0 - t * 0.08) + fbm(c * 3.0 + t * 0.03));
  o = over(o, vec3(0.8, 0.85, 1.0) * flick, beam * (0.18 + 0.38 * smoke) * (1.0 - 0.6 * onScreen));
  o = over(o, vec3(0.95, 0.97, 1.0) * flick, smoothstep(width * 0.35, 0.0, abs(bd.x - bd.y * 0.05)) * step(bd.y, 0.0) * step(0.17, c.y + 0.21) * 0.16 * (1.0 - 0.6 * onScreen));
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    vec2 at = vec2(hash(vec2(fk, 1.0)) - 0.5, hash(vec2(fk, 2.0)) * 0.5 + 0.2) + vec2(noise(vec2(t * 0.15, fk)) - 0.5, noise(vec2(fk, t * 0.12)) - 0.5) * 0.12;
    vec2 ad = at - bo;
    float aw = mix(0.02, 0.42, clamp(-ad.y / 0.45, 0.0, 1.0));
    float inBeam = smoothstep(aw, aw * 0.5, abs(ad.x - ad.y * 0.05));
    o = over(o, vec3(1.0, 0.97, 0.9), exp(-length(c - at) * (600.0 + 400.0 * hash(vec2(fk, 3.0)))) * inBeam * flick);
  }
  // the rows of seats in perspective, their tops lit by the screen, heads in silhouette here and there
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float ry = -0.15 - fk * fk * 0.035 - fk * 0.07;
    float sc = 1.0 + fk * 0.55;
    float sw = 0.085 * sc;
    float sx = (c.x + fk * 0.031) / sw;
    float seat = fract(sx) - 0.5;
    float top = ry + 0.05 * sc - 0.012 * sc * seat * seat * 4.0;
    float back = step(abs(seat), 0.44) * step(c.y, top) * step(ry - 0.12 * sc, c.y);
    vec3 red = vec3(0.32, 0.03, 0.05) * (0.5 + 0.5 * smoothstep(top - 0.03 * sc, top, c.y) * flick) * (0.8 + 0.2 * sin(seat * 12.0));
    o = over(o, red * (1.0 - fk * 0.15), back);
    float who = step(0.45 + fk * 0.13, hash(vec2(floor(sx), fk)));
    float bob = 0.003 * sc * sin(t * (0.7 + hash(vec2(floor(sx), fk + 5.0))) + floor(sx));
    vec2 hq = vec2(seat * sw, c.y - top - 0.03 * sc - bob) / 0.85;
    float head = smoothstep(0.03 * sc, 0.027 * sc, length(hq * vec2(1.0, 0.85))) + step(abs(hq.x), 0.04 * sc) * step(hq.y, -0.01 * sc) * step(-0.05 * sc, hq.y) * step(abs(hq.x), 0.035 * sc + (-hq.y) * 0.8);
    o = over(o, vec3(0.03, 0.02, 0.03) + glow * 0.04 * smoothstep(0.0, 0.03 * sc, hq.y), clamp(head, 0.0, 1.0) * who);
  }
  o.rgb *= mix(0.4, 1.0, smoothstep(1.15, 0.3, length(c * vec2(0.7, 1.0))));
  o.rgb += (hash(gl_FragCoord.xy + fract(t) * 91.0) - 0.5) * 0.03;
