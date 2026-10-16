// Portalab — ambient/soapbubbles: the « soapbubbles » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.75, 0.85), smoothstep(0.7, 0.0, length(uv - vec2(0.0, 1.0))) * 0.06);
  o = over(o, vec3(0.6, 0.85, 1.0), smoothstep(0.7, 0.0, length(uv - vec2(1.0, 0.0))) * 0.06);
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float life = 9.0 + 6.0 * hash(vec2(fi, 1.0));
    float tt = t + hash(vec2(fi, 2.0)) * life;
    float slot = floor(tt / life);
    float ph = fract(tt / life);
    float rad = 0.03 + 0.07 * hash(vec2(slot, fi + 3.0));
    float popAt = 0.55 + 0.45 * hash(vec2(slot, fi + 4.0));
    vec2 c = vec2(aspect * hash(vec2(slot, fi + 5.0)) + sin(ph * 6.0 + fi) * 0.04 + ph * 0.15 * (hash(vec2(slot, fi + 6.0)) - 0.5),
                  -0.12 + ph * 1.25);
    vec2 d = p - c;
    if (ph < popAt) {
      float ang = atan(d.y, d.x);
      float wob = 1.0 + 0.014 * sin(ang * 3.0 + t * 2.0 + fi) + 0.007 * sin(ang * 5.0 - t * 3.0);
      float dist = length(d) / (rad * wob);
      float film = fbm(d / rad * 1.4 + vec2(t * 0.25, fi * 3.0)) + dist * 0.4 + t * 0.05;
      vec3 irid = 0.5 + 0.5 * cos(6.2831 * (film * 1.6 + vec3(0.0, 0.33, 0.67)));
      float body = smoothstep(1.0, 0.96, dist);
      float rim = smoothstep(0.8, 1.0, dist) * body;
      o = over(o, mix(irid, vec3(1.0), 0.25), body * 0.05 + rim * 0.55);
      vec2 l = d / rad;
      float win = smoothstep(0.2, 0.1, length((l - vec2(-0.38, 0.42)) * vec2(1.0, 1.6)));
      float win2 = smoothstep(0.1, 0.04, length(l - vec2(0.42, -0.45)));
      o = over(o, vec3(1.0), (win * 0.75 + win2 * 0.4) * body);
    } else {
      float k = (ph - popAt) / 0.04;
      float fade = 1.0 - clamp(k, 0.0, 1.0);
      float ring = smoothstep(0.003, 0.0, abs(length(d) - rad * (1.0 + k * 0.6)));
      float ang = atan(d.y, d.x);
      float bits = step(0.7, fract(ang * 9.0 / 6.2831 + fi)) * smoothstep(0.006, 0.0, abs(length(d) - rad * (1.0 + k * 1.4)));
      o = over(o, vec3(0.9, 0.95, 1.0), (ring * 0.5 + bits * 0.8) * fade);
    }
  }
  gl_FragColor = o;
}