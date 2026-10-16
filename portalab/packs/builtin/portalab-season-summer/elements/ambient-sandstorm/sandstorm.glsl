// Portalab — ambient/sandstorm: the « sandstorm » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = 0.55 + 0.3 * sin(t * 0.31) + 0.2 * sin(t * 0.97 + 1.3) + 0.1 * sin(t * 2.3);
  vec2 q = p * vec2(1.6, 2.2);
  vec2 w1 = vec2(fbm(q * 0.9 + vec2(-t * 0.22 * gust, t * 0.05)), fbm(q * 0.9 + vec2(4.1 - t * 0.18, 1.7 + t * 0.07)));
  vec2 w2 = vec2(fbm(q * 1.7 + w1 * 2.0 + vec2(-t * 0.35, 0.0)), fbm(q * 1.7 + w1 * 2.0 + vec2(8.3, -t * 0.1)));
  float d = fbm(q * 1.1 + w2 * 2.4 + vec2(-t * 0.5 * gust, 0.0));
  float dense = smoothstep(0.28, 0.95, d) * (0.45 + 0.45 * gust);
  float streak = fbm(vec2(q.x * 0.6 - t * 1.3 * gust, q.y * 16.0 + w1.x * 3.0));
  dense += smoothstep(0.62, 0.85, streak) * 0.1;
  vec3 col = mix(vec3(0.45, 0.26, 0.11), vec3(0.97, 0.78, 0.5), clamp(d + 0.2 * w2.y, 0.0, 1.0));
  float a = clamp(dense, 0.0, 1.0) * 0.68 + 0.06 + 0.06 * gust;
  gl_FragColor = vec4(col * a, a);
}