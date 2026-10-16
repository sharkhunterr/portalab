// Portalab — ambient/acrylicpour: the « acrylicpour » ambience (spec 028, B2)
vec3 paintColour(float x) {
  x = fract(x);
  vec3 c0 = vec3(0.55, 0.12, 0.16);
  vec3 c1 = vec3(0.86, 0.36, 0.2);
  vec3 c2 = vec3(0.98, 0.52, 0.42);
  vec3 c3 = vec3(0.96, 0.7, 0.28);
  vec3 c4 = vec3(0.98, 0.9, 0.76);
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
  vec2 q = p * 1.1 + vec2(t * 0.01, 0.0);
  vec2 w = vec2(fbm(q + vec2(0.0, t * 0.02)), fbm(q + vec2(4.1, -t * 0.015)));
  vec2 r = q + w * 1.8;
  float v = fbm(r);
  vec3 col = paintColour(v * 1.5 + 0.2);
  // cells where the paints meet: rings of the lighter paint breaking through
  float zone = smoothstep(0.08, 0.0, abs(v - 0.52)) + smoothstep(0.06, 0.0, abs(v - 0.38)) * 0.7;
  float cellNoise = noise(r * 14.0 + w * 3.0);
  float cells = smoothstep(0.08, 0.0, abs(cellNoise - 0.55)) * zone;
  float holes = smoothstep(0.6, 0.7, cellNoise) * zone;
  col = mix(col, vec3(0.98, 0.93, 0.85), clamp(cells * 0.9 + holes * 0.5, 0.0, 1.0));
  float vein = 1.0 - abs(2.0 * fbm(r * 2.0 + 7.0) - 1.0);
  col = mix(col, vec3(1.0, 0.8, 0.35), smoothstep(0.96, 0.995, vein) * 0.8);
  gl_FragColor = over(vec4(0.0), col, 0.24 + 0.42 * edgeOf(uv));
}