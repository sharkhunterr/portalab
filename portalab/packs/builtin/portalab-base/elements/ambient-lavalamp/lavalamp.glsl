// Portalab — ambient/lavalamp: the « lavalamp » ambience (spec 028, B2)
vec3 waxColour(int i) {
  return i == 0 ? vec3(1.0, 0.25, 0.6) : i == 1 ? vec3(1.0, 0.55, 0.12) : i == 2 ? vec3(1.0, 0.85, 0.2)
       : i == 3 ? vec3(0.15, 0.82, 0.82) : i == 4 ? vec3(0.6, 0.35, 1.0) : i == 5 ? vec3(0.55, 0.9, 0.3)
       : i == 6 ? vec3(1.0, 0.4, 0.4) : i == 7 ? vec3(0.3, 0.6, 1.0) : vec3(1.0, 0.65, 0.85);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(1.0, 0.45, 0.6), vec3(0.45, 0.35, 1.0), uv.y), 0.07);
  float field = 0.0;
  vec2 grad = vec2(0.0);
  vec3 col = vec3(0.0);
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float h1 = hash(vec2(fi, 1.0));
    float h2 = hash(vec2(fi, 2.0));
    float speed = 0.05 + 0.05 * h2;
    float ph = t * speed + fi * 1.9;
    // lingering at the bottom and the top, moving in between
    float cyc = sin(ph);
    float y = 0.5 - 0.62 * cyc * (1.2 - 0.2 * cyc * cyc);
    float vy = abs(cos(ph));
    float x = aspect * (0.08 + 0.84 * h1) + 0.06 * sin(t * 0.07 + fi * 2.7);
    float r = 0.085 + 0.09 * hash(vec2(fi, 3.0));
    float stretch = 1.0 + 0.45 * vy;
    vec2 d = (p - vec2(x, y)) * vec2(1.0, 1.0 / stretch);
    float f = 1.7 * exp(-dot(d, d) / (r * r));
    field += f;
    grad += -2.0 * f / (r * r) * d;
    col += waxColour(i) * f * f;
  }
  // the pool of wax at the bottom and a little at the top
  float pool = 1.4 * exp(-max(p.y, 0.0) * 13.0) * (0.85 + 0.15 * sin(p.x * 6.0 + t * 0.2));
  float cap = 0.5 * exp(-max(1.0 - p.y, 0.0) * 16.0);
  field += pool + cap;
  grad += vec2(0.0, -13.0 * pool + 16.0 * cap);
  col += vec3(1.0, 0.35, 0.55) * pool * pool + vec3(0.5, 0.4, 1.0) * cap * cap;
  col /= max(max(max(col.r, col.g), col.b), 1e-4); // the colour of whichever blob is nearest, blended where they meet
  float body = smoothstep(0.95, 1.1, field);
  float glow = smoothstep(0.7, 1.0, field) * (1.0 - body);
  vec3 n = normalize(vec3(-grad * 0.035, 1.0));
  vec3 l = normalize(vec3(-0.4, 0.5, 0.8));
  float diff = clamp(dot(n, l), 0.0, 1.0);
  float spec = pow(clamp(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 24.0);
  float rimDark = smoothstep(1.6, 1.0, field);
  vec3 wax = col * (0.55 + 0.6 * diff) * (1.0 - 0.25 * rimDark) + vec3(1.0) * spec * 0.7;
  float edge = smoothstep(0.2, 0.6, length((uv - 0.5) * vec2(1.25, 1.0)));
  o = over(o, col, glow * 0.07);
  o = over(o, wax, body * (0.6 + 0.3 * edge));
  gl_FragColor = o;
}