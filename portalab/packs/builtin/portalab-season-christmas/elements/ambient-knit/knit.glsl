// Portalab — ambient/knit: the « knit » ambience (spec 028, B2)
float loop_(vec2 c, float side) {
  vec2 q = c - vec2(side * 0.22, 0.05);
  float a = side * 0.55;
  q = mat2(cos(a), -sin(a), sin(a), cos(a)) * q;
  return 1.0 - length(q / vec2(0.24, 0.5));
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  vec2 b = p + vec2(sin(p.y * 3.0 + t * 0.4), cos(p.x * 2.5 + t * 0.3)) * 0.006;
  vec2 g = b * vec2(34.0, 26.0);
  vec2 id = floor(g);
  vec2 c = fract(g) - 0.5;
  float l = loop_(c, -1.0);
  float r = loop_(c, 1.0);
  float stitch = max(l, r);
  float yarn = smoothstep(0.0, 0.15, stitch);
  float fibre = 0.8 + 0.2 * sin((c.x + c.y * (l > r ? 1.0 : -1.0)) * 60.0 + hash(id) * 6.0);
  // rows of colour and a small motif
  float row = mod(id.y, 14.0);
  vec3 cream = vec3(0.95, 0.88, 0.75);
  vec3 rust = vec3(0.72, 0.28, 0.14);
  vec3 mustard = vec3(0.88, 0.64, 0.22);
  vec3 col = row < 2.0 ? rust : row < 3.0 ? cream : row < 4.0 ? mustard : row < 10.0 ? cream : row < 11.0 ? mustard : row < 12.0 ? cream : rust;
  float mx = mod(id.x, 8.0);
  float my = row - 4.0;
  float motif = step(0.0, my) * step(my, 5.0) * step(abs(mx - 3.5) + abs(my - 2.5), 2.5) * step(1.5, abs(mx - 3.5) + abs(my - 2.5));
  col = mix(col, rust, motif);
  float lit = 0.75 + 0.35 * smoothstep(0.0, 0.45, stitch) - 0.2 * smoothstep(0.0, 0.3, c.y + 0.3);
  vec3 wool = col * lit * fibre;
  float edge = smoothstep(0.22, 0.6, length((uv - 0.5) * vec2(1.25, 1.0)));
  float breathe = 0.92 + 0.08 * sin(t * 0.5);
  o = over(o, vec3(0.2, 0.08, 0.04), (1.0 - yarn) * (0.05 + 0.33 * edge));
  o = over(o, wool * breathe, yarn * (0.06 + 0.6 * edge));
  o = over(o, vec3(1.0, 0.6, 0.25), smoothstep(1.0, 0.0, uv.y) * 0.04);
  gl_FragColor = o;
}