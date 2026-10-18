// Olympus — the booster stage on the summit: a golden sky, sunbeams fanning, a marble temple behind (pediment and
  // columns), a sea of clouds rolling below lit by far lightning, an eagle circling.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.98, 0.8, 0.5), vec3(0.4, 0.55, 0.85), smoothstep(-0.2, 0.6, c.y)), 1.0);
  vec2 sc = c - vec2(0.0, 0.25);
  o = over(o, vec3(1.0, 0.95, 0.75), pow(0.5 + 0.5 * sin(atan(sc.y, sc.x) * 12.0 + t * 0.15), 5.0) * smoothstep(1.2, 0.1, length(sc)) * 0.35);
  // the temple: a stylobate, columns, an architrave and a pediment
  float base = -0.12;
  float cols = step(0.45, fract(c.x * 9.0 + 0.5)) * step(fract(c.x * 9.0 + 0.5), 0.8) * step(abs(c.x), 0.62) * step(base, c.y) * step(c.y, 0.22);
  float lintel = step(abs(c.x), 0.68) * step(0.22, c.y) * step(c.y, 0.27);
  float ped = step(0.27, c.y) * step(c.y, 0.27 + 0.16 * (1.0 - abs(c.x) / 0.7)) * step(abs(c.x), 0.7);
  float steps = step(abs(c.x), 0.72) * step(base - 0.04, c.y) * step(c.y, base);
  float temple = clamp(cols + lintel + ped + steps, 0.0, 1.0);
  o = over(o, mix(vec3(0.82, 0.8, 0.76), vec3(0.98, 0.96, 0.92), smoothstep(-0.1, 0.4, c.y) * (0.85 + 0.15 * sin(c.x * 120.0))), temple * 0.92);
  // the sea of clouds, lit from inside by far lightning now and then
  float ph = mod(t, 6.0);
  float flash = exp(-abs(ph - 4.2) * 12.0) + 0.6 * exp(-abs(ph - 4.45) * 16.0);
  float cl = fbm(vec2(c.x * 2.5 + t * 0.04, c.y * 5.0 - t * 0.02)) + (-0.18 - c.y) * 3.0;
  vec3 cloudc = mix(vec3(0.62, 0.64, 0.74), vec3(0.75, 0.8, 1.0), flash * smoothstep(0.6, 0.0, abs(c.x + 0.5)));
  o = over(o, cloudc, smoothstep(0.35, 0.6, cl) * 0.8);
  // the clouds sink into a dusk blue below, so Portalab's words under the cards stay legible
  o = over(o, vec3(0.16, 0.2, 0.34), smoothstep(-0.15, -0.5, c.y) * 0.75);
  // an eagle circling high
  float ang = t * 0.25;
  vec2 q = (c - vec2(cos(ang) * 0.5, 0.42 + sin(ang) * 0.05)) * 70.0;
  o = over(o, vec3(0.25, 0.18, 0.1), step(abs(q.x), 3.5) * smoothstep(0.6, 0.0, abs(q.y - abs(q.x) * (0.3 + 0.12 * sin(t * 1.5)))));
  o.rgb *= mix(0.6, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
