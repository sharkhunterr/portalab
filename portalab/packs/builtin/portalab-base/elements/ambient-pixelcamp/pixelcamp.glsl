// Portalab — ambient/pixelcamp: the « pixelcamp » ambience (spec 028, B2)
float bayer2(vec2 a) {
  a = floor(a);
  return fract(dot(a, vec2(0.5, a.y * 0.75)));
}
float bayer4(vec2 a) {
  return bayer2(0.5 * a) * 0.25 + bayer2(a);
}
// a two-colour gradient the old way: v from 0 to 1 picks a or b, the dither mixing them in between
vec3 dither(vec3 a, vec3 b, float v, vec2 px) {
  return step(bayer4(px), clamp(v, 0.0, 1.0)) > 0.5 ? b : a;
}

float pine(vec2 px, float x0, float h) {
  float y = px.y;
  float w = (h - y) * 0.42 - mod(y, 7.0) * 0.6 + 2.0;
  return step(0.0, y) * step(y, h) * step(abs(px.x - x0), max(w, 0.0)) + step(abs(px.x - x0), 1.0) * step(y, 3.0) * step(-2.0, y);
}
void main() {
  float rows = 180.0;
  vec2 px = floor(gl_FragCoord.xy / u_res.y * rows);
  float W = floor(u_res.x / u_res.y * rows);
  float t = u_time;
  float tf = floor(t * 8.0) / 8.0;
  vec4 o = vec4(0.0);
  float gy = 30.0;
  // sky, dithered from deep blue to the purple of the horizon
  float sv = (px.y - 60.0) / 110.0;
  vec3 sky = sv < 0.5 ? dither(vec3(0.17, 0.11, 0.27), vec3(0.12, 0.09, 0.23), sv * 2.0, px) : dither(vec3(0.12, 0.09, 0.23), vec3(0.06, 0.07, 0.18), sv * 2.0 - 1.0, px);
  o = over(o, sky, 0.55);
  float sh = hash(px);
  float star = step(0.994, sh) * step(0.3, fract(sh * 91.0 + floor(t * 2.0 + sh * 10.0) * 0.37));
  vec2 bc = floor(px / 16.0);
  vec2 bs = bc * 16.0 + floor(vec2(hash(bc), hash(bc + 7.0)) * 14.0) + 1.0;
  vec2 bd = abs(px - bs);
  float big = step(0.75, hash(bc + 3.0)) * step(bd.x + bd.y, 1.0 + step(0.5, sin(t * 2.0 + hash(bc) * 30.0)));
  o = over(o, vec3(1.0, 0.95, 0.8), clamp(star + big, 0.0, 1.0) * step(90.0, px.y));
  vec2 moon = vec2(floor(W * 0.82), 150.0);
  float m = step(length(px - moon), 9.0) * step(5.5, length(px - moon - vec2(4.0, 3.0)));
  o = over(o, vec3(1.0, 0.95, 0.72), m);
  // mountains with snow caps
  float peak = 60.0 + 26.0 * abs(fract(px.x / 70.0 + 0.3) - 0.5) * -2.0 + 26.0 + 8.0 * hash(vec2(floor(px.x / 70.0 + 0.3), 1.0));
  float mount = step(px.y, peak);
  o = over(o, mix(vec3(0.16, 0.13, 0.26), vec3(0.8, 0.82, 0.95), step(peak - 5.0, px.y)), mount);
  // pines, the far row bluer
  float far = 0.0;
  float cell = floor(px.x / 13.0);
  far = pine(vec2(px.x, px.y - gy - 4.0), cell * 13.0 + 6.0 + floor(hash(vec2(cell, 2.0)) * 3.0), 22.0 + floor(hash(vec2(cell, 3.0)) * 18.0));
  o = over(o, vec3(0.1, 0.16, 0.2), clamp(far, 0.0, 1.0));
  float near = 0.0;
  float c2 = floor((px.x + 9.0) / 23.0);
  float keep = step(0.45, hash(vec2(c2, 4.0)));
  near = pine(vec2(px.x, px.y - gy + 1.0), c2 * 23.0 - 9.0 + 11.0, 34.0 + floor(hash(vec2(c2, 5.0)) * 22.0)) * keep;
  float fireX = floor(W * 0.55);
  near *= step(40.0, abs(px.x - fireX));
  o = over(o, vec3(0.04, 0.09, 0.08), clamp(near, 0.0, 1.0));
  // the ground, the firelight on it
  float ground = step(px.y, gy);
  o = over(o, dither(vec3(0.05, 0.1, 0.07), vec3(0.08, 0.15, 0.09), hash(floor(px / 2.0)) * 0.6, px), ground);
  float flick = 0.08 * sin(t * 9.0) + 0.05 * sin(t * 23.0);
  float light = 1.0 - length((px - vec2(fireX, gy + 4.0)) * vec2(1.0, 1.8)) / (62.0 + flick * 30.0);
  o = over(o, vec3(1.0, 0.55, 0.2), step(bayer4(px), light * 0.7) * 0.28);
  // the tent, its side facing the fire lit
  float tx = floor(W * 0.36);
  vec2 tq = px - vec2(tx, gy);
  float tent = step(0.0, tq.y) * step(abs(tq.x), 20.0 - tq.y * 0.8);
  float door = step(0.0, tq.y) * step(abs(tq.x - 2.0), 6.0 - tq.y * 0.4) * step(tq.y, 14.0);
  o = over(o, tq.x > 0.0 ? vec3(0.85, 0.45, 0.2) : vec3(0.45, 0.22, 0.12), tent);
  o = over(o, vec3(0.12, 0.05, 0.04), door * tent);
  o = over(o, vec3(0.3, 0.18, 0.1), step(abs(tq.x), 0.5) * step(tq.y, 27.0) * step(25.0, tq.y));
  // the traveller on a log, warm on the fire side
  vec2 sq = px - vec2(fireX - 20.0, gy);
  float log_ = step(abs(sq.x), 7.0) * step(0.0, sq.y) * step(sq.y, 2.0);
  float bodyM = step(abs(sq.x), 3.0) * step(3.0, sq.y) * step(sq.y, 11.0);
  float head = step(length(sq - vec2(0.0, 14.0)), 2.6);
  o = over(o, vec3(0.32, 0.18, 0.1), log_);
  o = over(o, mix(vec3(0.3, 0.2, 0.35), vec3(1.0, 0.6, 0.3), step(2.0, sq.x)), clamp(bodyM + head, 0.0, 1.0));
  o = over(o, vec3(0.7, 0.2, 0.2), step(abs(sq.x), 3.0) * step(abs(sq.y - 11.0), 0.5)); // a scarf
  o = over(o, vec3(0.3, 0.2, 0.35), step(abs(sq.x - 4.0 - 0.0), 3.0) * step(abs(sq.y - 7.0 + (sq.x - 4.0) * 0.3), 0.6)); // an arm to the fire
  // the fire: stones, logs, flames frame by frame
  vec2 fq = px - vec2(fireX, gy);
  float stones = step(abs(fq.y - 1.0), 1.0) * step(9.0, abs(fq.x)) * step(abs(fq.x), 12.0) * step(0.3, hash(vec2(floor(fq.x / 2.0), 9.0)));
  o = over(o, vec3(0.45, 0.45, 0.5), stones);
  float logs = step(abs(fq.y - 2.0 - fq.x * 0.25), 1.0) * step(abs(fq.x), 8.0) + step(abs(fq.y - 2.0 + fq.x * 0.25), 1.0) * step(abs(fq.x), 8.0);
  o = over(o, vec3(0.35, 0.18, 0.08), clamp(logs, 0.0, 1.0));
  float fh = 24.0 * (1.0 - abs(fq.x) / 12.0) + 4.0 * sin(tf * 7.0 + fq.x * 0.7);
  float flame = (1.0 - (fq.y - 3.0) / max(fh, 1.0)) + (noise(vec2(fq.x * 0.35, fq.y * 0.25 - tf * 5.0)) - 0.5) * 0.9;
  flame *= step(3.0, fq.y) * step(abs(fq.x), 12.0);
  vec3 fc = flame > 0.8 ? vec3(1.0, 0.96, 0.7) : flame > 0.55 ? vec3(1.0, 0.8, 0.2) : flame > 0.35 ? vec3(1.0, 0.45, 0.1) : vec3(0.8, 0.15, 0.05);
  o = over(o, fc, step(0.18, flame));
  // smoke and sparks rising
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float ph = fract(hash(vec2(fi, 1.0)) + t * (0.25 + 0.2 * hash(vec2(fi, 2.0))));
    vec2 s = vec2(fireX + floor(sin(ph * 9.0 + fi) * 6.0), gy + 18.0 + floor(ph * 60.0));
    o = over(o, vec3(1.0, 0.7, 0.25), step(length(px - s), 0.6) * step(0.4, fract(t * 3.0 + fi * 0.3)) * (1.0 - ph));
  }
  float sm = noise(vec2(px.x * 0.12 - t * 0.3, px.y * 0.08 - t * 0.6));
  float column = smoothstep(14.0, 0.0, abs(px.x - fireX - (px.y - gy - 26.0) * 0.35)) * step(gy + 26.0, px.y) * smoothstep(110.0, 50.0, px.y);
  o = over(o, vec3(0.55, 0.55, 0.6), step(bayer4(px), sm * column * 0.7) * 0.5);
  // fireflies among the pines
  vec2 ff = floor(px / 9.0);
  vec2 fp = ff * 9.0 + floor(vec2(hash(ff + 1.0), hash(ff + 2.0)) * 8.0) + floor(vec2(sin(t + hash(ff) * 9.0), cos(t * 0.8 + hash(ff) * 7.0)) * 1.5);
  float fly = step(0.93, hash(ff + 4.0)) * step(length(px - fp), 0.6) * step(0.5, sin(t * 2.0 + hash(ff) * 20.0)) * step(gy, px.y) * step(px.y, 75.0);
  o = over(o, vec3(0.8, 1.0, 0.4), fly);
  gl_FragColor = o;
}