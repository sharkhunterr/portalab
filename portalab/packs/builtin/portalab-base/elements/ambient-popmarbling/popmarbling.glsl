// Portalab — ambient/popmarbling: the « popmarbling » ambience (spec 028, B2)
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
  vec2 q = p;
  q.y += 0.08 * sin(q.x * 4.0 + t * 0.1);
  q.x += 0.06 * sin(q.y * 9.0 - t * 0.07);
  q.y += 0.04 * sin(q.x * 13.0 + t * 0.05);
  q += 0.25 * vec2(fbm(q * 1.5 + t * 0.02), fbm(q * 1.5 + 3.0 - t * 0.02));
  float stripes = q.y * 5.0 + fbm(q * 3.0) * 1.2;
  vec3 col = paintColour(stripes * 0.5);
  float line = smoothstep(0.08, 0.0, abs(fract(stripes * 2.0) - 0.5) - 0.42);
  col = mix(col, vec3(0.35, 0.08, 0.1), line * 0.5);
  gl_FragColor = over(vec4(0.0), col, 0.24 + 0.42 * edgeOf(uv));
}