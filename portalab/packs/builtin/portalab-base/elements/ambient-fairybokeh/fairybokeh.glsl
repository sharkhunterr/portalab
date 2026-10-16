// Portalab — ambient/fairybokeh: the « fairybokeh » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.5, 0.2, 0.08), 0.06);
  for (int l = 0; l < 3; l++) {
    float fl = float(l);
    float cell = 0.06 + fl * 0.07;
    vec2 g = (p + vec2(t * (0.004 + fl * 0.006), sin(t * 0.2 + fl) * 0.01)) / cell + fl * 3.7;
    vec2 id = floor(g);
    vec2 f = fract(g) - 0.5;
    float h = hash(id + fl * 11.0);
    if (h > (fl == 0.0 ? 0.78 : 0.5 + fl * 0.08)) {
      vec2 off = (vec2(hash(id + 1.0), hash(id + 2.0)) - 0.5) * 0.3;
      float r = 0.12 + 0.1 * fl + 0.08 * hash(id + 3.0);
      float d = length(f - off);
      float soft = 0.02 + fl * 0.06;
      float disc = smoothstep(r, r - soft, d);
      float rim = smoothstep(r - soft - 0.06, r - soft, d) * disc;
      float pick = hash(id + 4.0);
      vec3 col = pick < 0.4 ? vec3(1.0, 0.68, 0.3) : pick < 0.7 ? vec3(1.0, 0.82, 0.5) : pick < 0.88 ? vec3(1.0, 0.55, 0.35) : vec3(0.98, 0.45, 0.5);
      float tw = 0.6 + 0.4 * sin(t * (0.6 + hash(id + 5.0) * 1.5) + h * 30.0);
      float a = (fl == 0.0 ? 0.4 : fl == 1.0 ? 0.24 : 0.15) * tw;
      o = over(o, col, disc * a + rim * a * 0.6);
      o = over(o, col, exp(-d * 9.0) * a * 0.25);
    }
  }
  gl_FragColor = o;
}