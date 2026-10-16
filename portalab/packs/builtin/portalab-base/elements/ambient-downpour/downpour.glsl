// Portalab — ambient/downpour: the « downpour » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec3 col = vec3(0.0);
  float a = 0.0;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float density = 30.0 + fi * 30.0;
    float length_ = 4.0 + fi * 2.5;
    vec2 r = vec2(p.x * density + p.y * density * 0.08, p.y * length_ + t * (5.0 + fi * 2.2));
    vec2 id = floor(r);
    vec2 f = fract(r);
    float h2 = hash(id * 1.3 + fi * 7.0);
    float drop = step(0.58, hash(id + fi * 17.0)) * smoothstep(0.035, 0.0, abs(f.x - 0.2 - 0.6 * h2))
      * smoothstep(0.0, 0.35, f.y) * smoothstep(1.0, 0.5 + 0.35 * h2, f.y);
    float w = 0.32 - fi * 0.06;
    col += vec3(0.7, 0.78, 0.9) * drop * w * 2.0;
    a = max(a, drop * w);
  }
  vec2 s = vec2(p.x * 9.0, 0.0);
  float cell = floor(s.x);
  float born = hash(vec2(cell, floor(t * 1.5)));
  float age = fract(t * 1.5);
  float ring = abs(length(vec2(fract(s.x) - 0.5, (uv.y - 0.035) * 40.0)) - age * 0.4);
  float splash = step(0.55, born) * smoothstep(0.03, 0.0, ring) * (1.0 - age) * step(uv.y, 0.07);
  col += vec3(0.75, 0.82, 0.95) * splash;
  a = max(a, splash * 0.6);
  float mist = fbm(vec2(p.x * 2.0 + t * 0.1, p.y * 3.0)) * smoothstep(0.3, 0.0, uv.y);
  col += vec3(0.55, 0.6, 0.7) * mist * 0.5;
  a = max(a, mist * 0.35);
  gl_FragColor = vec4(col * a, a);
}