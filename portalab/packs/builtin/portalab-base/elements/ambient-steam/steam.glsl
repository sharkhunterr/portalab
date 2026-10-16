// Portalab — ambient/steam: the « steam » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.55, 0.2), smoothstep(0.45, 0.0, uv.y) * 0.16);
  float wisps = 0.0;
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    vec2 q = vec2(p.x * (2.0 + fl), p.y * 1.4 - t * (0.1 + fl * 0.05)) + fl * 7.0;
    vec2 w = vec2(fbm(q + vec2(0.0, t * 0.04)), fbm(q + vec2(5.2, -t * 0.03)));
    float f = fbm(q + w * 2.2);
    float curl = 1.0 - abs(2.0 * f - 1.0);
    wisps += pow(smoothstep(0.75, 1.0, curl), 2.5) * (0.8 - fl * 0.3);
  }
  float rise = smoothstep(0.7, 0.1, uv.y) * smoothstep(-0.05, 0.1, uv.y);
  vec3 col = mix(vec3(1.0, 0.72, 0.45), vec3(1.0, 0.95, 0.9), smoothstep(0.0, 0.7, uv.y));
  o = over(o, col, clamp(wisps * rise, 0.0, 1.0) * 0.4);
  gl_FragColor = o;
}