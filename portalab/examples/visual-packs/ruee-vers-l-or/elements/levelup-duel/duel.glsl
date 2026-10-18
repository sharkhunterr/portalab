// High noon duel — a level-up over the whole stage (gl_FragCoord, u_res, u_age): the sun blazing, heat
  // shimmering, dust blowing, a tumbleweed crossing; at 2.2 s a shot — a flash and a ring — and a sheriff's
  // star opening round the new level.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.8, 5.6, tl);
  o = over(o, mix(vec3(0.85, 0.55, 0.25), vec3(0.98, 0.85, 0.55), smoothstep(-0.5, 0.5, c.y)), 0.75 * fade);
  vec2 sun = c - vec2(0.0, 0.32);
  o = over(o, vec3(1.0, 0.97, 0.85), (smoothstep(0.07, 0.06, length(sun)) + exp(-length(sun) * 5.0) * 0.5) * fade);
  float dust = fbm(vec2(c.x * 4.0 - tl * 0.8, c.y * 8.0)) * smoothstep(0.0, -0.4, c.y);
  o = over(o, vec3(0.8, 0.6, 0.35), dust * 0.6 * fade);
  vec2 tw = c - vec2(-0.9 + tl * 0.3, -0.3 + 0.03 * abs(sin(tl * 5.0)));
  float rr = length(tw);
  o = over(o, vec3(0.45, 0.32, 0.18), smoothstep(0.05, 0.045, rr) * (0.4 + 0.6 * step(0.5, fract(atan(tw.y, tw.x) * 3.0 + tl * 6.0 + rr * 50.0))) * fade);
  float shot = exp(-abs(tl - 2.2) * 14.0);
  o = over(o, vec3(1.0), shot * 0.7 * fade);
  float r = length(c);
  o = over(o, vec3(1.0, 0.9, 0.6), smoothstep(0.01, 0.0, abs(r - (tl - 2.2) * 0.5)) * step(2.2, tl) * smoothstep(3.4, 2.4, tl) * fade);
  float open = smoothstep(2.3, 3.0, tl);
  float a = atan(c.y, c.x);
  float star = 0.17 + 0.07 * (0.5 + 0.5 * cos(a * 5.0 - 1.5708));
  o = over(o, vec3(0.95, 0.72, 0.25), smoothstep(0.012, 0.0, abs(r - star * (0.8 + 0.4 * open))) * open * fade);
  o = over(o, vec3(1.0, 0.9, 0.55), exp(-r * 6.0) * open * 0.4 * fade);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
