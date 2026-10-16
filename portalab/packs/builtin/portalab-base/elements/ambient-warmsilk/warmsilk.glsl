// Portalab — ambient/warmsilk: the « warmsilk » ambience (spec 028, B2)
float folds(vec2 p, float t) {
  return sin(p.x * 5.5 + sin(p.y * 3.2 + t * 0.21) * 1.8 + t * 0.12)
       + 0.5 * sin(p.x * 9.0 - p.y * 4.5 + t * 0.17 + sin(p.x * 2.1 + t * 0.09) * 2.0)
       + 0.25 * sin(p.y * 12.0 + p.x * 2.5 - t * 0.23);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  float h = folds(p, t);
  float e = 0.004;
  vec2 grad = vec2(folds(p + vec2(e, 0.0), t) - h, folds(p + vec2(0.0, e), t) - h) / e;
  vec3 n = normalize(vec3(-grad * 0.09, 1.0));
  vec3 light = normalize(vec3(-0.5, 0.6, 0.65));
  float diff = clamp(dot(n, light), 0.0, 1.0);
  float sheen = pow(clamp(dot(reflect(-light, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 18.0);
  vec3 base = mix(vec3(0.7, 0.28, 0.12), vec3(0.95, 0.5, 0.35), 0.5 + 0.25 * h);
  base = mix(base, vec3(1.0, 0.62, 0.2), smoothstep(0.3, 0.9, noise(p * 0.8 + t * 0.02)));
  vec3 col = base * (0.35 + 0.75 * diff) + vec3(1.0, 0.9, 0.75) * sheen * 0.8;
  float edge = smoothstep(0.2, 0.62, length((uv - 0.5) * vec2(1.3, 1.0)));
  o = over(o, col, 0.12 + 0.4 * edge);
  gl_FragColor = o;
}