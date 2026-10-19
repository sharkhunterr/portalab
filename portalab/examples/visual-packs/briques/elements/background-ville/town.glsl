// Town being built HD — a profile background (u_res, u_time, hash, noise, fbm, over): a blue sky and its clouds,
// a green plate, buildings of bricks in running bond rising brick by brick — each one popping in with a flash
// and a bounce — their studs on top, windows; every 16 s the town is built again.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.62, 0.82, 1.0), vec3(0.3, 0.55, 0.95), uv.y), 1.0);
  float cl = fbm(vec2(c.x * 3.0 + t * 0.02, uv.y * 5.0));
  o = over(o, vec3(1.0), smoothstep(0.55, 0.7, cl) * smoothstep(0.35, 0.7, uv.y) * 0.9);
  o = over(o, vec3(1.0, 0.95, 0.7), smoothstep(0.08, 0.07, length(c - vec2(aspect * 0.85, 0.82))));
  float ground = 0.12;
  o = over(o, vec3(0.16, 0.6, 0.29), step(uv.y, ground));
  float tl = mod(t, 16.0);
  vec2 bs = vec2(0.08, 0.04);
  float row = floor((uv.y - ground) / bs.y);
  vec2 g = vec2((c.x + 0.5 * bs.x * mod(row, 2.0)) / bs.x, (uv.y - ground) / bs.y);
  vec2 id = floor(g);
  vec2 f = fract(g);
  float building = floor(id.x / 4.0);
  float height = 3.0 + floor(hash(vec2(building, 1.0)) * 9.0);
  float gap = step(3.5, mod(id.x, 4.0) + 0.5 * step(0.5, hash(vec2(building, 2.0))));
  float order = id.y * 4.0 + mod(id.x, 4.0);
  float appear = 0.6 + order * 0.07 + hash(vec2(building, 3.0)) * 2.0;
  float since = tl - appear;
  float exists = step(id.y, height - 1.0) * step(0.0, id.y) * step(0.0, since) * (1.0 - gap);
  float h = hash(vec2(building, 4.0) + id * 0.0);
  float hb = hash(id);
  vec3 col = hb < 0.3 ? vec3(0.84, 0.16, 0.16) : (hb < 0.5 ? vec3(0.97, 0.77, 0.12) : (hb < 0.75 ? vec3(0.12, 0.44, 0.84) : vec3(0.95, 0.95, 0.92)));
  col = mix(col, vec3(0.95, 0.95, 0.92), step(0.7, h) * 0.6);
  float edge = smoothstep(0.0, 0.06, f.x) * smoothstep(1.0, 0.94, f.x) * smoothstep(0.0, 0.1, f.y) * smoothstep(1.0, 0.9, f.y);
  col *= 0.7 + 0.3 * edge + 0.15 * smoothstep(0.5, 1.0, f.y);
  float win = step(0.3, f.x) * step(f.x, 0.7) * step(0.3, f.y) * step(f.y, 0.75) * step(0.6, hash(id + 9.0)) * step(1.0, id.y);
  col = mix(col, vec3(0.75, 0.9, 1.0), win);
  col += vec3(1.0) * exp(-max(since, 0.0) * 12.0) * 0.6;
  float pop = 1.0 - 0.15 * exp(-max(since, 0.0) * 18.0);
  o = over(o, col, exists * step(abs(f.y - 0.5), 0.5 * pop + 0.01));
  float topRow = step(height, id.y) * step(id.y, height) * step(0.0, tl - (0.6 + (height - 1.0) * 4.0 * 0.07 + hash(vec2(building, 3.0)) * 2.0)) * (1.0 - gap);
  float stud = topRow * step(f.y, 0.22) * step(0.5, fract(f.x * 2.0 + 0.25)) * step(abs(fract(f.x * 2.0) - 0.5), 0.3);
  o = over(o, vec3(0.9, 0.9, 0.88), stud * step(uv.y, 1.0));
  o.rgb *= mix(0.88, 1.0, smoothstep(1.2, 0.3, length(uv - 0.5)));
  gl_FragColor = o;
}
