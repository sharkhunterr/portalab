// Portalab — ambient/poppaint: the « poppaint » ambience (spec 028, B2)
vec3 paintColour(float x) {
  x = fract(x);
  vec3 c0 = vec3(0.55, 0.2, 0.95);
  vec3 c1 = vec3(1.0, 0.18, 0.55);
  vec3 c2 = vec3(1.0, 0.55, 0.1);
  vec3 c3 = vec3(1.0, 0.86, 0.15);
  vec3 c4 = vec3(0.1, 0.82, 0.8);
  float b = 0.035;
  vec3 c = mix(c0, c1, smoothstep(0.2 - b, 0.2 + b, x));
  c = mix(c, c2, smoothstep(0.4 - b, 0.4 + b, x));
  c = mix(c, c3, smoothstep(0.6 - b, 0.6 + b, x));
  c = mix(c, c4, smoothstep(0.8 - b, 0.8 + b, x));
  return mix(c, c0, smoothstep(0.96, 1.0, x));
}
float edgeOf(vec2 uv) {
  return smoothstep(0.18, 0.62, length((uv - 0.5) * vec2(1.25, 1.0)));
}

void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 1.1;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    q += 0.3 * vec2(sin(q.y * 1.7 + t * 0.06 + fi * 1.7), cos(q.x * 1.4 - t * 0.05 + fi * 2.3));
  }
  float v = noise(q * 0.8 + vec2(t * 0.012, -t * 0.008)) * 0.65 + noise(q * 1.7 - t * 0.01) * 0.35;
  vec3 col = paintColour(v * 1.6 + 0.04 * sin(t * 0.03));
  float streak = 0.95 + 0.05 * sin(v * 70.0 + q.x * 2.0);
  float sheen = smoothstep(0.6, 1.0, noise(q * 3.0 + t * 0.02)) * 0.12;
  gl_FragColor = over(vec4(0.0), col * streak + sheen, 0.26 + 0.4 * edgeOf(uv));
}