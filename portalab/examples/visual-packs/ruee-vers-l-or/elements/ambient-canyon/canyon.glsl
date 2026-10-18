// Canyon at dusk — an ambience behind the whole portal (u_res, u_time, hash, noise, fbm, over): a dusk
// sky low on the screen, mesas in silhouette, vultures circling high, a tumbleweed rolling across. See-through above.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  float glow = smoothstep(0.45, 0.0, uv.y);
  o = over(o, mix(vec3(0.9, 0.45, 0.2), vec3(0.4, 0.15, 0.25), uv.y * 2.0), glow * 0.4);
  float shimmer = 0.004 * sin(uv.y * 120.0 + t * 3.0) * smoothstep(0.3, 0.1, uv.y);
  float mx = c.x + shimmer;
  float mesa = 0.12 + 0.1 * step(0.5, fract(mx * 0.9 + 0.2)) * step(fract(mx * 0.9 + 0.2), 0.8) + 0.05 * step(0.6, fract(mx * 2.3)) * step(fract(mx * 2.3), 0.75) + 0.015 * noise(vec2(mx * 20.0, 1.0));
  o = over(o, vec3(0.16, 0.07, 0.06), step(uv.y, mesa) * 0.85);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float ang = t * (0.15 + 0.05 * fk) + fk * 2.1;
    vec2 v = vec2(aspect * (0.3 + 0.2 * fk) + cos(ang) * 0.12, 0.8 + sin(ang) * 0.04);
    vec2 q = (c - v) * 90.0;
    float flap = sin(t * 2.0 + fk) * 0.3;
    float bird = step(abs(q.x), 3.0) * smoothstep(0.5, 0.0, abs(q.y - abs(q.x) * (0.25 + flap * 0.1)));
    o = over(o, vec3(0.08, 0.04, 0.03), bird * 0.6);
  }
  vec2 tw = c - vec2(mod(t * 0.06, aspect + 0.4) - 0.2, 0.06 + 0.02 * abs(sin(t * 3.0)));
  float rr = length(tw);
  float weed = smoothstep(0.035, 0.03, rr) * (0.4 + 0.6 * step(0.5, fract(atan(tw.y, tw.x) * 3.0 + t * 4.0 + rr * 60.0)));
  o = over(o, vec3(0.45, 0.32, 0.18), weed * 0.7);
  gl_FragColor = o;
}
