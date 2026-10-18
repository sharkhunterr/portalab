// Campfire — a profile background (u_res, u_time, hash, noise, fbm, over): a night sky with stars, a fire
// flickering low in the middle, embers rising and fading.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.03, 0.02, 0.06), vec3(0.08, 0.05, 0.1), uv.y), 0.95);
  vec2 sg = c * 60.0;
  o = over(o, vec3(0.9, 0.9, 1.0), step(0.985, hash(floor(sg))) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * step(0.4, uv.y));
  vec2 f = c - vec2(aspect * 0.5, 0.1);
  float flame = fbm(vec2(f.x * 10.0, f.y * 6.0 - t * 3.0)) * smoothstep(0.08 + f.y * 0.2, 0.0, abs(f.x)) * step(0.0, f.y) * smoothstep(0.3, 0.0, f.y);
  o = over(o, mix(vec3(1.0, 0.85, 0.3), vec3(1.0, 0.3, 0.05), smoothstep(0.0, 0.2, f.y)), clamp(flame * 2.0, 0.0, 1.0));
  o = over(o, vec3(1.0, 0.5, 0.15), exp(-length(f) * 4.0) * 0.3);
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    float life = fract(t * 0.25 + hash(vec2(fk, 1.0)));
    vec2 e = vec2(aspect * 0.5 + (hash(vec2(fk, 2.0)) - 0.5) * 0.2 + 0.03 * sin(life * 10.0 + fk), 0.12 + life * 0.6);
    o = over(o, vec3(1.0, 0.6, 0.2), exp(-length(c - e) * 400.0) * (1.0 - life));
  }
  gl_FragColor = o;
}
