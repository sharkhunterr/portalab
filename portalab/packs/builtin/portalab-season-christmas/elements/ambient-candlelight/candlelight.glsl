// Portalab — ambient/candlelight: the « candlelight » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.25, 0.1, 0.04), smoothstep(0.3, 0.95, length((uv - 0.5) * vec2(1.1, 1.0))) * 0.45);
  float light = 0.0;
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    vec2 base = i == 0 ? vec2(0.06, 0.12) : i == 1 ? vec2(0.3, 0.0) : i == 2 ? vec2(0.68, 0.02) : i == 3 ? vec2(0.95, 0.18) : i == 4 ? vec2(0.03, 0.75) : vec2(0.97, 0.82);
    vec2 c = vec2(base.x * aspect, base.y) + vec2(noise(vec2(t * 1.3, fi)) - 0.5, noise(vec2(fi, t * 1.1)) - 0.5) * 0.02;
    float flick = 0.75 + 0.18 * noise(vec2(t * 5.0, fi * 7.0)) + 0.1 * noise(vec2(t * 13.0, fi * 3.0)) - 0.12 * step(0.97, hash(vec2(floor(t * 8.0), fi)));
    float d = length(p - c);
    light += (exp(-d * 4.5) * 0.6 + exp(-d * 16.0) * 0.5) * flick;
  }
  float shade = 0.75 + 0.25 * fbm(p * 1.6 + vec2(sin(t * 0.7), cos(t * 0.5)) * 0.15);
  light *= shade;
  o = over(o, vec3(1.0, 0.55, 0.18), clamp(light, 0.0, 1.0) * 0.55);
  o = over(o, vec3(1.0, 0.85, 0.55), smoothstep(0.7, 1.4, light) * 0.35);
  gl_FragColor = o;
}