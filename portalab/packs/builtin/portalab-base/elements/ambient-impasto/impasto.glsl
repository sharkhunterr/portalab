// Portalab — ambient/impasto: the « impasto » ambience (spec 028, B2)
float fbm4(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
vec3 popInk(float u) {
  float x = fract(u) * 6.0;
  float i = floor(x);
  float f = fract(x);
  vec3 a = i < 1.0 ? vec3(1.0, 0.2, 0.6) : i < 2.0 ? vec3(1.0, 0.86, 0.12) : i < 3.0 ? vec3(0.2, 0.72, 1.0)
         : i < 4.0 ? vec3(1.0, 0.55, 0.1) : i < 5.0 ? vec3(0.45, 0.25, 0.88) : vec3(0.97, 0.96, 1.0);
  vec3 b = i < 1.0 ? vec3(1.0, 0.86, 0.12) : i < 2.0 ? vec3(0.2, 0.72, 1.0) : i < 3.0 ? vec3(1.0, 0.55, 0.1)
         : i < 4.0 ? vec3(0.45, 0.25, 0.88) : i < 5.0 ? vec3(0.97, 0.96, 1.0) : vec3(1.0, 0.2, 0.6);
  return mix(a, b, smoothstep(0.86, 1.0, f));
}
// lights paint of this colour whose surface slopes by grad
vec3 litPaint(vec2 grad, vec3 ink) {
  vec3 n = normalize(vec3(-grad, 1.0));
  vec3 l = normalize(vec3(-0.45, 0.6, 0.65));
  float diff = clamp(dot(n, l), 0.0, 1.0);
  float spec = pow(clamp(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 36.0);
  return ink * (0.45 + 0.7 * diff) + vec3(1.0) * spec * 0.85;
}

float bands(vec2 p, float t, float aspect) {
  vec2 c = vec2(aspect * (0.55 + 0.08 * sin(t * 0.05)), 0.5 + 0.1 * cos(t * 0.04));
  vec2 d = p - c;
  float r = length(d);
  float a = atan(d.y, d.x) + 1.1 / (r + 0.35) + t * 0.035;
  vec2 q = vec2(cos(a), sin(a)) * r;
  q += 0.22 * vec2(fbm4(q * 2.0 + t * 0.02), fbm4(q * 2.0 + 5.3 - t * 0.02));
  return r * 1.1 + fbm4(q * 1.6) * 1.7 + q.x * 0.3;
}
float relief(float u) {
  // smooth from one colour to the next: no crease where two colours meet (it lit as a crack)
  return (0.5 - 0.5 * cos(u * 6.0 * 6.2831)) * 0.6 + 0.008 * sin(u * 260.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  float e = 2.5 / u_res.y;
  float u = bands(p, t, aspect);
  float ux = bands(p + vec2(e, 0.0), t, aspect);
  float uy = bands(p + vec2(0.0, e), t, aspect);
  float h = relief(u);
  vec2 grad = vec2(relief(ux) - h, relief(uy) - h) / e * 0.018;
  vec3 col = litPaint(grad, popInk(u));
  float edge = smoothstep(0.18, 0.62, length((uv - 0.5) * vec2(1.25, 1.0)));
  gl_FragColor = over(vec4(0.0), col, 0.3 + 0.55 * edge);
}