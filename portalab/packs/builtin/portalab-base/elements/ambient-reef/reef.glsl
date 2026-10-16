// Portalab — ambient/reef: the « reef » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.0, 0.07, 0.16), smoothstep(0.75, 0.0, uv.y) * 0.4);
  // the surface seen from below
  vec2 sfc = vec2(p.x * 4.0, p.y * 9.0);
  float n = fbm(sfc + fbm(sfc * 0.8 + t * 0.35) * 1.5 + vec2(t * 0.1, 0.0));
  float cells = smoothstep(0.35, 0.8, n) * (0.7 + 0.3 * sin(p.x * 30.0 + n * 8.0 + t * 1.5));
  float surface = smoothstep(0.72, 0.96, uv.y);
  o = over(o, mix(vec3(0.05, 0.35, 0.55), vec3(0.75, 0.95, 1.0), cells), surface * (0.45 + 0.5 * cells));
  // rays swaying down
  float rx = p.x + (1.0 - uv.y) * (0.25 + sin(t * 0.35) * 0.15);
  float rays = pow(0.5 + 0.5 * sin(rx * 11.0 + sin(rx * 3.0 + t * 0.4) * 1.5), 4.0)
    * (0.5 + 0.5 * fbm(vec2(rx * 6.0, t * 0.2))) * smoothstep(0.1, 0.95, uv.y);
  o = over(o, vec3(0.5, 0.85, 1.0), rays * 0.38 * (1.0 - surface));
  // caustics on the depths
  vec2 cw = vec2(noise(p * 3.0 + t * 0.3), noise(p * 3.0 + vec2(4.0, -t * 0.25)));
  float cn = noise(p * 11.0 + cw * 2.2) * 0.7 + noise(p * 23.0 + cw * 3.0 + t * 0.2) * 0.3;
  float caustic = smoothstep(0.58, 0.78, cn) * smoothstep(0.32, 0.0, uv.y);
  o = over(o, vec3(0.45, 0.85, 1.0), caustic * 0.4);
  // a jellyfish: a bell that contracts and relaxes, drifting up and sideways, its threads trailing
  float cycle = 34.0;
  float life = mod(t, cycle) / cycle;
  vec2 jp = vec2(aspect * (0.15 + 0.7 * life), 0.25 + 0.4 * life + 0.03 * sin(t * 0.7));
  float beat = 0.5 + 0.5 * sin(t * 2.2);
  vec2 jq = p - jp;
  vec2 bellR = vec2(0.055 + 0.012 * beat, 0.04 - 0.008 * beat);
  float bellD = length(jq / bellR);
  float bell = smoothstep(1.0, 0.85, bellD) * step(-0.004, jq.y);
  float rim = smoothstep(0.12, 0.0, abs(bellD - 0.95)) * step(-0.004, jq.y);
  float threads = 0.0;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float x0 = (fi - 2.0) * 0.018;
    float y = -jq.y;
    float wave = sin(y * 40.0 - t * 3.0 + fi) * 0.008 * (y / 0.15);
    threads += smoothstep(0.0022, 0.0, abs(jq.x - x0 - wave)) * step(0.0, y) * smoothstep(0.17, 0.02, y);
  }
  vec3 jelly = vec3(0.75, 0.6, 1.0);
  o = over(o, jelly, bell * 0.18 + rim * 0.55);
  o = over(o, jelly * 1.1, threads * 0.45);
  o = over(o, vec3(0.9, 0.8, 1.0), exp(-length(jq) * 30.0) * 0.25 * (0.6 + 0.4 * beat));
  gl_FragColor = o;
}