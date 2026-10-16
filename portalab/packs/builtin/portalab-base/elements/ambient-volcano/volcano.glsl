// Portalab — ambient/volcano: the « volcano » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 vent = vec2(aspect * 0.68, 0.42);
  // eruptions: some slots erupt, the glow surges with them
  float slot = floor(t / 3.5);
  float ph = mod(t, 3.5);
  float erupting = step(0.45, hash(vec2(slot, 1.0)));
  float surge = erupting * exp(-ph * 1.2);
  // the air shimmering above the lava
  vec2 shimmer = vec2(noise(vec2(p.x * 9.0, uv.y * 14.0 - t * 2.5)) - 0.5, 0.0) * 0.012 * smoothstep(0.5, 0.15, uv.y);
  vec2 pw = p + shimmer;
  // the plume: ash billowing up from the vent, lit red from below, crackling with lightning
  vec2 r = vec2((pw.x - vent.x) * 1.5, uv.y * 1.9 - t * 0.12);
  vec2 wr = vec2(fbm(r + t * 0.05), fbm(r + vec2(6.1, 2.3)));
  float ash = fbm(r * 1.3 + wr * 2.2);
  float column = smoothstep(0.1 + (uv.y - vent.y) * 1.2, 0.0, abs(pw.x - vent.x - (uv.y - vent.y) * 0.35))
    * smoothstep(vent.y - 0.02, vent.y + 0.04, uv.y);
  float plume = (smoothstep(0.22, 0.7, ash) + smoothstep(0.35, 0.0, uv.y - vent.y) * 0.45) * column;
  vec3 smoke = mix(vec3(0.26, 0.22, 0.21), vec3(0.6, 0.54, 0.52), ash);
  smoke += vec3(0.85, 0.2, 0.03) * smoothstep(vent.y + 0.35, vent.y, uv.y) * (0.45 + 0.6 * surge + 0.15 * sin(t * 1.3));
  o = over(o, smoke, clamp(plume, 0.0, 1.0) * 0.92);
  // volcanic lightning inside the plume
  float bslot = floor(t / 1.3);
  float bph = mod(t, 1.3);
  float strike = step(0.72, hash(vec2(bslot, 5.0))) * exp(-bph * 8.0);
  vec2 bAt = vent + vec2((hash(vec2(bslot, 6.0)) - 0.5) * 0.3, 0.25 + hash(vec2(bslot, 7.0)) * 0.3);
  float bx = bAt.x + (fbm(vec2(uv.y * 9.0, bslot)) - 0.5) * 0.12;
  float bolt = smoothstep(0.004, 0.0, abs(pw.x - bx)) * step(abs(uv.y - bAt.y), 0.09);
  o = over(o, vec3(0.75, 0.8, 1.0), clamp(bolt * 2.0 + exp(-length(pw - bAt) * 12.0) * 0.5, 0.0, 1.0) * strike);
  // the lava field
  vec2 q = vec2(pw.x * 3.0 + t * 0.04, uv.y * 7.0 - t * 0.05);
  vec2 w = vec2(fbm(q * 0.7 + t * 0.03), fbm(q * 0.7 + vec2(3.7, -t * 0.02)));
  float n = fbm(q + w * 1.6);
  float vein = smoothstep(0.06, 0.0, abs(n - 0.5)) + 0.5 * smoothstep(0.15, 0.0, abs(n - 0.5));
  float pulse = 0.75 + 0.25 * sin(t * 1.3 + n * 9.0) + 0.3 * surge;
  float field = smoothstep(0.3, 0.06, uv.y);
  vec3 lava = mix(vec3(0.9, 0.18, 0.02), vec3(1.0, 0.78, 0.3), clamp(vein - 0.4, 0.0, 1.0)) * pulse;
  vec3 crust = vec3(0.07, 0.03, 0.02) + vec3(0.22, 0.05, 0.0) * fbm(q * 3.0);
  o = over(o, mix(crust, lava, clamp(vein, 0.0, 1.0)), field * (0.6 + 0.4 * clamp(vein, 0.0, 1.0)));
  // the mountain: a dark cone up to the crater, lava streams running down its slopes
  float slope = vent.y - abs(pw.x - vent.x) * (0.62 + 0.08 * noise(vec2(pw.x * 6.0, 1.0)));
  float rough = (fbm(vec2(pw.x * 8.0, 3.0)) - 0.5) * 0.05;
  float mountain = smoothstep(0.004, -0.004, uv.y - slope - rough) * step(0.0, slope);
  vec3 rock = vec3(0.06, 0.04, 0.04) + vec3(0.09, 0.04, 0.03) * fbm(pw * 12.0);
  float stream = smoothstep(0.03, 0.0, abs(fbm(vec2(pw.x * 4.0, uv.y * 3.0 + t * 0.08)) - 0.5))
    * smoothstep(slope + 0.01, slope - 0.25, uv.y) * smoothstep(0.42, 0.05, abs(pw.x - vent.x));
  vec3 slopeCol = mix(rock, vec3(1.0, 0.45, 0.08) * pulse, clamp(stream * 1.5, 0.0, 1.0));
  o = over(o, slopeCol, mountain * 0.95);
  // the crater glowing
  float crater = exp(-length((pw - vent) * vec2(1.0, 3.0)) * 9.0);
  o = over(o, vec3(1.0, 0.5, 0.1), crater * (0.55 + 0.45 * surge));
  // lava bombs: thrown on arcs, cooling as they fly, a short glowing trail
  for (int i = 0; i < 10; i++) {
    float fi = float(i);
    float age = ph - hash(vec2(slot, fi + 20.0)) * 0.6;
    if (age < 0.0 || age > 2.4) continue;
    vec2 v0 = vec2((hash(vec2(slot, fi + 30.0)) - 0.5) * 0.5, 0.45 + hash(vec2(slot, fi + 40.0)) * 0.45);
    vec2 at = vent + v0 * age - vec2(0.0, 0.32) * age * age;
    vec2 back = vent + v0 * (age - 0.06) - vec2(0.0, 0.32) * (age - 0.06) * (age - 0.06);
    vec2 pa = pw - back;
    vec2 ba = at - back;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
    float trail = smoothstep(0.004, 0.0, length(pa - ba * h)) * h;
    float bomb = smoothstep(0.006, 0.0, length(pw - at));
    vec3 hot = mix(vec3(1.0, 0.85, 0.4), vec3(0.9, 0.2, 0.02), age / 2.4);
    o = over(o, hot, clamp(bomb + trail * 0.7, 0.0, 1.0) * erupting * step(0.05, at.y));
  }
  float glow = smoothstep(0.55, 0.08, uv.y) * 0.22 * pulse;
  o = over(o, vec3(0.7, 0.12, 0.0), glow);
  gl_FragColor = o;
}