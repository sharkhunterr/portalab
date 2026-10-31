// Saloon — the booster stage: the desert at sunset, a huge sun sinking behind the mesas, heat shimmering, dust
  // blowing along the ground, a hawk circling (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  vec3 sky = mix(vec3(0.98, 0.72, 0.36), vec3(0.42, 0.14, 0.2), smoothstep(-0.1, 0.55, c.y));
  o = vec4(sky, 1.0);
  // the sun, its halo, banded by the heat
  vec2 sc = c - vec2(0.0, -0.08);
  float sun = smoothstep(0.26, 0.25, length(sc));
  float bands = step(0.0, sin((c.y + 0.08) * 70.0 + t * 1.5)) * smoothstep(-0.02, -0.2, c.y);
  o = over(o, vec3(1.0, 0.6, 0.25), exp(-length(sc) * 3.0) * 0.6);
  o = over(o, vec3(1.0, 0.86, 0.45), sun * (1.0 - bands * 0.7));
  // the mesas, flat-topped, in silhouette
  float shimmer = 0.004 * sin(c.y * 120.0 + t * 6.0);
  float mx = c.x + shimmer;
  float m1 = 0.13 * clamp((0.26 - abs(mx + asp * 0.3)) / 0.06, 0.0, 1.0);
  float m2 = 0.09 * clamp((0.18 - abs(mx - asp * 0.33)) / 0.05, 0.0, 1.0);
  float m3 = 0.05 * clamp((0.1 - abs(mx - asp * 0.06)) / 0.04, 0.0, 1.0);
  float mesa = -0.2 + max(m1, max(m2, m3)) + 0.004 * noise(vec2(mx * 40.0, 0.0));
  o = over(o, vec3(0.32, 0.12, 0.1), step(c.y, mesa));
  // the desert floor, warm, darker near
  float floorY = -0.2;
  o = over(o, mix(vec3(0.62, 0.32, 0.16), vec3(0.3, 0.13, 0.07), smoothstep(floorY, -0.5, c.y)), step(c.y, floorY));
  // dust blowing along the ground
  float dust = fbm(vec2(c.x * 3.0 - t * 0.5, c.y * 8.0));
  o = over(o, vec3(0.95, 0.72, 0.45), smoothstep(0.5, 0.85, dust) * smoothstep(-0.05, -0.25, c.y) * 0.55);
  // a hawk circling high up
  vec2 hp = vec2(0.45 * cos(t * 0.5), 0.33 + 0.05 * sin(t * 0.5));
  vec2 hd = c - hp;
  float flap = 0.25 * sin(t * 3.0);
  float wing = smoothstep(0.006, 0.0, abs(hd.y - (0.35 + flap) * abs(hd.x) + 2.0 * hd.x * hd.x)) * step(abs(hd.x), 0.07);
  o = over(o, vec3(0.15, 0.06, 0.06), wing);
  o.rgb *= smoothstep(1.35, 0.35, length(c * vec2(0.8, 1.0)));
