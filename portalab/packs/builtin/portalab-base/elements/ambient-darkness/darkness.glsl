// Portalab — ambient/darkness: the « darkness » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 c = uv - 0.5;
  float rr = length(c * 2.0);
  vec2 dir = normalize(c * vec2(aspect, 1.0) + 1e-5);
  float breath = 0.5 + 0.5 * sin(t * 0.23) * sin(t * 0.11 + 1.0);
  float fing = fbm(dir * 2.2 + vec2(t * 0.035, -t * 0.027));
  fing = smoothstep(0.45, 0.8, fing);
  vec2 w = vec2(fbm(p * 3.0 + t * 0.04), fbm(p * 3.0 + vec2(4.0, -t * 0.05)));
  float wisp = fbm(p * 5.0 + w * 2.0 - dir * t * 0.06);
  float limit = 1.02 - 0.12 * breath - 0.5 * fing * (0.6 + 0.4 * breath) + (wisp - 0.5) * 0.22;
  float dark = smoothstep(limit - 0.03, limit + 0.1, rr);
  float throb = 0.5 + 0.5 * sin(t * 2.4);
  float rim = exp(-abs(rr - limit) * 16.0) * (1.0 - dark * 0.7);
  o = over(o, vec3(0.5, 0.02, 0.04), rim * (0.1 + 0.16 * throb));
  vec3 smoke = vec3(0.012, 0.006, 0.008) + vec3(0.035, 0.02, 0.025) * smoothstep(0.4, 0.9, wisp);
  o = over(o, smoke, dark * 0.96);
  // veins: thin red lines running inwards along the fingers, pulsing
  float ridge = 1.0 - abs(2.0 * fbm(p * 4.0 + w * 1.6 - dir * t * 0.03) - 1.0);
  float vein = smoothstep(0.95, 0.995, ridge) * smoothstep(limit + 0.02, limit + 0.3, rr);
  o = over(o, vec3(0.7, 0.03, 0.04), vein * (0.12 + 0.22 * throb));
  // eyes: three pairs at their own rhythm, deep in the dark
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float life = 5.0 + fi * 1.7;
    float slot = floor((t + fi * 2.1) / life);
    float ph = fract((t + fi * 2.1) / life) * life;
    float shown = step(0.35, hash(vec2(slot, fi + 4.0)));
    float a = 6.2831 * hash(vec2(slot, fi + 1.0));
    float d0 = 0.84 + 0.1 * hash(vec2(slot, fi + 2.0));
    vec2 at = 0.5 + vec2(cos(a), sin(a)) * 0.5 * d0;
    at = clamp(at, vec2(0.05, 0.08), vec2(0.95, 0.92));
    float size = 0.7 + 0.9 * hash(vec2(slot, fi + 3.0));
    vec2 e = vec2((uv.x - at.x) * aspect, uv.y - at.y) / size;
    float blink = step(0.12, abs(ph - life * 0.45));
    float open = smoothstep(0.0, 0.9, ph) * smoothstep(life - 0.4, life - 1.2, ph) * blink;
    float look = sin(t * 0.9 + fi * 3.0) * 0.004;
    float gap = 0.024;
    float eyes = 0.0;
    float slit = 0.0;
    for (int j = 0; j < 2; j++) {
      vec2 d = e - vec2(j == 0 ? -gap : gap, 0.0);
      d.y *= j == 0 ? 1.0 : 1.08;
      float almond = 1.0 - length(vec2(d.x / 0.013, d.y / (0.0065 * max(open, 0.05)) + abs(d.x) * 30.0));
      float inside = smoothstep(0.0, 0.25, almond);
      eyes += inside;
      slit += inside * smoothstep(0.0028, 0.0012, abs(d.x - look));
    }
    float glow = exp(-length(e * vec2(0.6, 1.4)) * 28.0) * 0.4;
    float on = open * shown;
    o = over(o, vec3(0.8, 0.05, 0.02), glow * on);
    o = over(o, mix(vec3(1.0, 0.25, 0.05), vec3(1.0, 0.85, 0.35), clamp(eyes, 0.0, 1.0) * 0.7), clamp(eyes, 0.0, 1.0) * on);
    o = over(o, vec3(0.05, 0.0, 0.0), clamp(slit, 0.0, 1.0) * on * 0.9);
  }
  gl_FragColor = o;
}