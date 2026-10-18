// Olympus clouds — a profile background (u_res, u_time, hash, noise, fbm, over): a sky above the clouds, a row of
// marble columns, clouds rolling below them, and every few seconds a bolt of lightning lighting it all.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.95, 0.85, 0.65), vec3(0.45, 0.62, 0.85), uv.y), 1.0);
  float cx = fract(c.x * 4.0);
  float col = step(0.35, cx) * step(cx, 0.65) * step(0.3, uv.y) * step(uv.y, 0.78);
  float flute = 0.9 + 0.1 * sin(cx * 60.0);
  o = over(o, vec3(0.96, 0.94, 0.9) * flute, col);
  o = over(o, vec3(0.92, 0.9, 0.86), step(0.78, uv.y) * step(uv.y, 0.84));
  o = over(o, vec3(0.85, 0.82, 0.76), step(0.84, uv.y) * step(uv.y, 0.86));
  float cloud = fbm(vec2(c.x * 3.0 + t * 0.05, uv.y * 4.0)) + (0.38 - uv.y) * 2.5;
  o = over(o, vec3(1.0, 0.98, 0.96), smoothstep(0.45, 0.6, cloud));
  float ph = mod(t, 7.0);
  float flash = exp(-abs(ph - 5.0) * 10.0) + 0.6 * exp(-abs(ph - 5.25) * 14.0);
  float bx = aspect * 0.8 + 0.03 * sin(uv.y * 30.0) + 0.05 * (noise(vec2(uv.y * 12.0, floor(t / 7.0))) - 0.5);
  o = over(o, vec3(1.0, 1.0, 0.85), smoothstep(0.006, 0.0, abs(c.x - bx)) * step(0.5, uv.y) * flash);
  o = over(o, vec3(1.0, 1.0, 0.95), flash * 0.25);
  gl_FragColor = o;
}
