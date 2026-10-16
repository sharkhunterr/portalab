// Portalab — ambient/amberglow: the « amberglow » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.9, 0.45, 0.15), smoothstep(0.35, 0.95, length((uv - 0.5) * vec2(1.2, 1.0))) * 0.14);
  float field = 0.0;
  vec3 col = vec3(0.0);
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    float h1 = hash(vec2(fi, 1.0));
    float h2 = hash(vec2(fi, 2.0));
    vec2 c = vec2(aspect * (0.5 + 0.46 * sin(t * (0.03 + 0.03 * h1) + fi * 2.1)), 0.5 + 0.62 * sin(t * (0.05 + 0.04 * h2) + fi * 1.3));
    float r = 0.1 + 0.12 * hash(vec2(fi, 3.0));
    vec2 d = p - c;
    float f = r * r / max(dot(d, d), 1e-4);
    vec3 hue = i == 0 || i == 4 ? vec3(1.0, 0.55, 0.15) : i == 1 || i == 5 ? vec3(0.95, 0.35, 0.3) : i == 2 ? vec3(1.0, 0.75, 0.3) : vec3(0.85, 0.38, 0.15);
    field += f;
    col += hue * f;
  }
  col /= max(field, 1e-4);
  float glow = smoothstep(0.7, 1.4, field);
  float core = smoothstep(1.2, 4.0, field);
  o = over(o, mix(col, vec3(1.0, 0.86, 0.6), core * 0.4), glow * 0.22 + core * 0.1);
  o = over(o, vec3(1.0, 0.85, 0.6), (hash(gl_FragCoord.xy + floor(t * 12.0)) - 0.5) * 0.04 + 0.02);
  gl_FragColor = o;
}