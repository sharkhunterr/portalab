// Face down, between the sprocket holes: the projector's light turning slowly behind the reel, the film's base
  // catching it, grain and a little flicker — every card alike (a back never tells the rarity).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float frame = floor(t * 12.0);
  float flick = 0.9 + 0.1 * hash(vec2(frame, 5.0));
  vec3 col = mix(vec3(0.16, 0.12, 0.08), vec3(0.06, 0.045, 0.03), smoothstep(0.0, 0.7, length(c)));
  float a = atan(c.y, c.x);
  col += vec3(1.0, 0.85, 0.55) * pow(0.5 + 0.5 * sin(a * 10.0 + t * 0.4), 6.0) * smoothstep(0.7, 0.1, length(c)) * 0.22 * flick;
  col += vec3(1.0, 0.85, 0.6) * exp(-length(c) * 4.0) * 0.25 * flick;
  col += vec3(1.0, 0.95, 0.85) * smoothstep(0.08, 0.0, abs(c.x + c.y * 0.4 - mod(t * 0.25, 2.4) + 1.2)) * 0.12;
  col += (hash(gl_FragCoord.xy + frame) - 0.5) * 0.06;
  o = vec4(col, 1.0);
