// Portalab — ambient/thunderstorm: the « thunderstorm » ambience (spec 028, B2)
float bolt(vec2 p, float x0, float top, float seed, float width) {
  // a jagged path down from the clouds: coarse turns and fine jitter
  float y = p.y;
  float x = x0 + (fbm(vec2(y * 2.2, seed)) - 0.5) * 0.55 + (noise(vec2(y * 18.0, seed * 3.0)) - 0.5) * 0.05;
  float d = abs(p.x - x);
  float along = step(top, y) * smoothstep(top, top + 0.04, y) * step(y, 1.05);
  return along * (smoothstep(width, 0.0, d) + exp(-d * 55.0) * 0.35);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  // strikes at random moments: one chance per slot of 2.3 s
  float slot = floor(t / 2.3);
  float ph = mod(t, 2.3);
  float strikes = step(0.55, hash(vec2(slot, 3.1)));
  float flicker = exp(-ph * 10.0) + 0.8 * exp(-abs(ph - 0.16) * 22.0) + 0.4 * exp(-abs(ph - 0.31) * 30.0);
  float flash = strikes * flicker;
  float bx = (0.12 + 0.76 * hash(vec2(slot, 7.0))) * aspect;
  vec2 strikeAt = vec2(bx, 0.78);
  // clouds: two layers drifting at their own pace, a domain warp folding them
  vec2 q = vec2(p.x * 1.3 + t * 0.025, p.y * 2.2);
  vec2 w = vec2(fbm(q * 1.1 + t * 0.03), fbm(q * 1.1 + vec2(5.0, -t * 0.02)));
  float c1 = fbm(q + w * 1.4);
  float c2 = fbm(q * 2.3 + w * 2.0 + vec2(t * 0.05, 0.0));
  float cloud = smoothstep(0.26, 0.72, c1 * 0.7 + c2 * 0.3) * smoothstep(0.25, 0.85, uv.y);
  // dark heavy bellies, lighter rims where the cloud thins
  vec3 col = mix(vec3(0.2, 0.21, 0.27), vec3(0.55, 0.58, 0.68), smoothstep(0.35, 0.85, c2));
  col *= 0.8 + 0.35 * smoothstep(0.4, 0.9, uv.y);
  // lightning lights the clouds from inside, strongest around the strike
  float near = exp(-length((p - strikeAt) * vec2(1.0, 1.6)) * 2.2);
  col += vec3(0.6, 0.65, 0.9) * cloud * flash * (0.35 + 1.4 * near);
  // distant sheet lightning: a glow wandering in the clouds
  float far = step(0.8, hash(vec2(floor(t / 1.1), 11.0))) * exp(-mod(t, 1.1) * 6.0);
  vec2 farAt = vec2(hash(vec2(floor(t / 1.1), 2.0)) * aspect, 0.85);
  col += vec3(0.45, 0.5, 0.75) * cloud * far * exp(-length(p - farAt) * 3.0) * 0.9;
  float a = cloud * 0.9;
  // the bolt and two branches, fading after the first flicker
  float life = strikes * exp(-ph * 3.2);
  float b = bolt(p, bx, 0.18, slot, 0.0035);
  float br1 = bolt(vec2(p.x - (0.62 - p.y) * 0.25, p.y), bx + 0.02, 0.42, slot + 4.0, 0.0022)
    * step(p.y, 0.62);
  float br2 = bolt(vec2(p.x + (0.5 - p.y) * 0.35, p.y), bx - 0.03, 0.3, slot + 9.0, 0.0018)
    * step(p.y, 0.5) * step(0.5, hash(vec2(slot, 13.0)));
  float light = (b + br1 * 0.7 + br2 * 0.55) * life * flicker;
  col += vec3(0.86, 0.9, 1.0) * light * 2.5;
  a = max(a, clamp(light, 0.0, 1.0));
  // the whole sky brightens for an instant
  a = max(a, flash * 0.12);
  col += vec3(0.5, 0.55, 0.7) * flash * 0.12;
  gl_FragColor = vec4(col * a, a);
}