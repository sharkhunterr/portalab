// Portalab — ambient/paintribbon: the « paintribbon » ambience (spec 028, B2)
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

void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float base = fk == 0.0 ? 0.22 : 0.84;
    float amp = fk == 0.0 ? 0.11 : 0.05;
    float e = 2.5 / u_res.y;
    // the stroke's centre line and width, at the point and a little right and up (for the light)
    vec3 h3 = vec3(0.0);
    float u = 0.0;
    float inside = 0.0;
    for (int j = 0; j < 3; j++) {
      vec2 q = p + (j == 1 ? vec2(e, 0.0) : j == 2 ? vec2(0.0, e) : vec2(0.0));
      float mid = base + amp * sin(q.x * 2.1 + t * 0.28 + fk * 2.0) + amp * 0.45 * sin(q.x * 4.7 - t * 0.21 + fk);
      float w = (fk == 0.0 ? 0.15 : 0.05) * (0.75 + 0.35 * sin(q.x * 2.9 + t * 0.23 + fk * 3.0));
      float across = (q.y - mid) / w;
      float torn = 0.12 * (fbm4(vec2(q.x * 9.0, fk * 5.0 + t * 0.03)) - 0.5) * 2.0;
      float uu = across * 0.42 + fbm4(vec2(q.x * 2.5 - t * 0.05, across * 0.8 + fk * 7.0)) * 0.6 + fk * 0.37;
      float dome = sqrt(max(1.0 - across * across, 0.0));
      float hh = (dome * 0.8 + (0.5 - 0.5 * cos(uu * 6.0 * 6.2831)) * 0.35 + 0.01 * sin(uu * 260.0)) * 0.02;
      if (j == 0) {
        u = uu;
        inside = smoothstep(1.0 + torn, 0.92 + torn, abs(across));
        h3.x = hh;
      } else if (j == 1) {
        h3.y = hh;
      } else {
        h3.z = hh;
      }
    }
    vec3 col = litPaint(vec2(h3.y - h3.x, h3.z - h3.x) / e, popInk(u));
    o = over(o, col, inside * 0.95);
  }
  gl_FragColor = o;
}