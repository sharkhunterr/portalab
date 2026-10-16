// Portalab — ambient/abyss: the « abyss » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float n = fbm(p * 3.0 + fbm(p * 3.0 + t * 0.18) * 1.4 + t * 0.06);
  float n2 = fbm(p * 5.0 - fbm(p * 4.0 - t * 0.21) * 1.2 - t * 0.05);
  float caustic = pow(1.0 - abs(sin(n * 16.0)), 7.0) * pow(1.0 - abs(sin(n2 * 14.0)), 3.0) * 1.6;
  caustic *= smoothstep(0.05, 0.9, uv.y);
  float rays = (0.5 + 0.5 * sin(p.x * 9.0 + sin(p.x * 3.0 + t * 0.4) * 2.0 + t * 0.3))
    * (0.5 + 0.5 * sin(p.x * 23.0 - t * 0.5)) * smoothstep(0.25, 1.0, uv.y);
  vec3 col = vec3(0.35, 0.85, 1.0) * caustic + vec3(0.45, 0.8, 0.95) * rays * 0.35;
  float a = caustic * 0.5 + rays * 0.18;
  vec2 g = vec2(p.x * 9.0, p.y * 9.0 - t * 1.6);
  vec2 id = floor(g);
  float r = hash(id);
  vec2 wobble = vec2(sin(t * 2.0 + r * 9.0) * 0.2, 0.0);
  float ring = abs(length(fract(g) - 0.5 - wobble) - 0.07 - r * 0.06);
  float bubble = step(0.85, r) * smoothstep(0.025, 0.0, ring);
  col += vec3(0.8, 0.95, 1.0) * bubble;
  a = max(a, bubble * 0.7);
  col += vec3(0.0, 0.12, 0.22) * (1.0 - uv.y);
  a = max(a, (1.0 - uv.y) * 0.12);
  gl_FragColor = vec4(col * a, a);
}