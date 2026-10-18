// Clockmaker's workshop — a profile background (u_res, u_time, hash, noise, fbm, over): a lamp's warm glow,
// a wall of small gears turning, sparks flying from a grinder in a corner.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.1, 0.06, 0.03), vec3(0.22, 0.13, 0.06), uv.y), 0.9);
  o = over(o, vec3(1.0, 0.7, 0.35), exp(-length(c - vec2(aspect * 0.7, 0.8)) * 3.0) * 0.35);
  vec2 g = c * 7.0;
  vec2 cell = floor(g);
  vec2 q = fract(g) - 0.5;
  float dir = mod(cell.x + cell.y, 2.0) < 0.5 ? 1.0 : -1.0;
  float a = atan(q.y, q.x) + dir * t * 0.6;
  float r = length(q);
  float gear = smoothstep(0.02, 0.0, r - (0.36 + 0.05 * step(0.0, sin(a * 10.0)))) - smoothstep(0.02, 0.0, r - 0.12);
  o = over(o, vec3(0.7, 0.48, 0.2), clamp(gear, 0.0, 1.0) * 0.35 * step(0.4, hash(cell)));
  for (int k = 0; k < 24; k++) {
    float fk = float(k);
    float life = fract(t * 1.3 + hash(vec2(fk, 1.0)));
    vec2 sp = vec2(0.1, 0.15) + vec2(0.4 + 0.5 * hash(vec2(fk, 2.0)), 0.3 * hash(vec2(fk, 3.0))) * life - vec2(0.0, 0.3 * life * life);
    o = over(o, vec3(1.0, 0.75, 0.3), exp(-length(c - sp) * 300.0) * (1.0 - life));
  }
  gl_FragColor = o;
}
