// Portalab — ambient/neoncity: the « neoncity » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  float g = step(0.95, hash(vec2(floor(t * 3.0), 1.0)));
  float band = step(abs(uv.y - hash(vec2(floor(t * 3.0), 2.0))), 0.025);
  float x = p.x + g * band * (hash(vec2(floor(t * 3.0), 3.0)) - 0.5) * 0.15;
  float horizon = 0.5;
  vec4 o = vec4(0.0);
  if (uv.y > horizon) {
    float h = uv.y - horizon;
    // the sky: a dusk gradient, a striped sun sinking
    o = over(o, mix(vec3(0.55, 0.12, 0.45), vec3(0.06, 0.02, 0.15), smoothstep(0.0, 0.4, h)), smoothstep(0.45, 0.0, h) * 0.55);
    vec2 sun = vec2(aspect * 0.5, horizon + 0.12);
    float sd = length(vec2(x, uv.y) - sun);
    float stripes = step(0.0, sin((uv.y - horizon) * 140.0 - t * 1.5)) + step(0.14, uv.y - horizon);
    float disk = smoothstep(0.13, 0.125, sd) * min(stripes, 1.0);
    o = over(o, mix(vec3(1.0, 0.25, 0.5), vec3(1.0, 0.85, 0.3), smoothstep(-0.12, 0.12, uv.y - sun.y)), disk);
    o = over(o, vec3(1.0, 0.35, 0.6), exp(-sd * 9.0) * 0.35);
    // the skyline: towers of random heights, their windows lit
    float col = floor(x * 26.0);
    float tower = 0.03 + 0.17 * pow(hash(vec2(col, 4.0)), 1.8);
    float inTower = step(h, tower) * step(0.08, fract(x * 26.0));
    vec2 win = vec2(fract(x * 26.0 * 4.0), fract(h * 160.0));
    float lit = step(0.6, hash(vec2(col, floor(h * 160.0)) + floor(x * 104.0))) * step(0.3, win.x) * step(0.4, win.y);
    lit *= 0.6 + 0.4 * sin(t * 0.3 + hash(vec2(col, floor(h * 160.0))) * 20.0);
    o = over(o, vec3(0.03, 0.02, 0.07), inTower);
    o = over(o, mix(vec3(0.2, 0.9, 1.0), vec3(1.0, 0.4, 0.8), step(0.5, hash(vec2(col, 7.0)))), inTower * lit * 0.8);
    // flying cars: lights crossing the sky with a trail
    for (int i = 0; i < 4; i++) {
      float fi = float(i);
      float speed = 0.12 + hash(vec2(fi, 1.0)) * 0.2;
      float lane = horizon + 0.12 + fi * 0.07;
      float cx = mod(t * speed * (mod(fi, 2.0) * 2.0 - 1.0) + hash(vec2(fi, 2.0)) * 3.0, aspect + 0.6) - 0.3;
      float dx = (x - cx) * (mod(fi, 2.0) * 2.0 - 1.0);
      float car = exp(-length(vec2(dx, (uv.y - lane) * 3.0)) * 220.0);
      float trail = smoothstep(0.004, 0.0, abs(uv.y - lane)) * smoothstep(-0.2, 0.0, dx) * step(dx, 0.0);
      vec3 light = mix(vec3(1.0, 0.3, 0.3), vec3(0.4, 0.9, 1.0), mod(fi, 2.0));
      o = over(o, light, clamp(car * 2.0 + trail * 0.5, 0.0, 1.0));
    }
    gl_FragColor = o;
    return;
  }
  // the ground plane: roads to the horizon, blocks, data streaming toward the viewer
  float depth = horizon - uv.y;
  float z = 0.35 / depth;
  vec2 c = vec2((x - aspect * 0.5) * z * 2.2, z + t * 0.9);
  vec2 cell = floor(c);
  vec2 f = fract(c);
  float wRoad = 0.06 + 0.04 * hash(cell);
  float lineW = fwidthApprox(z);
  float road = max(smoothstep(wRoad + lineW, wRoad, f.x), smoothstep(wRoad + lineW, wRoad, f.y));
  float px = fract(t * (0.3 + hash(vec2(cell.y, 5.0)) * 0.7) + hash(vec2(cell.y, 9.0)));
  float py = fract(-t * (0.6 + hash(vec2(cell.x, 6.0)) * 0.9) + hash(vec2(cell.x, 8.0)));
  float pulse = smoothstep(wRoad * 1.4, 0.0, f.y) * exp(-abs(f.x - px) * 12.0)
    + smoothstep(wRoad * 1.4, 0.0, f.x) * exp(-max(f.y - py, 0.0) * 6.0) * step(py - 0.02, f.y);
  vec2 win = floor(f * 6.0);
  float lit = step(0.7, hash(cell * 13.0 + win)) * step(0.14, f.x) * step(0.14, f.y);
  lit *= 0.6 + 0.4 * sin(t * 0.6 + hash(cell + win) * 30.0);
  vec3 tint = mix(vec3(0.0, 0.85, 1.0), vec3(1.0, 0.2, 0.75), step(0.5, hash(cell)));
  float fade = smoothstep(0.0, 0.16, depth);
  o = over(o, tint, road * 0.45 * fade);
  o = over(o, tint, lit * 0.3 * fade);
  o = over(o, vec3(1.0, 0.95, 0.85), clamp(pulse, 0.0, 1.0) * fade);
  o = over(o, vec3(1.0, 0.35, 0.6), exp(-depth * 18.0) * 0.35); // the horizon's glow
  o = over(o, vec3(0.4, 0.9, 1.0), g * band * 0.3);
  gl_FragColor = o;
}