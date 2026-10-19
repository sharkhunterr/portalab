// A silent film behind the art (the card's panel: c in half heights): sepia, 24 frames a second — its
  // flicker, its gate weave, grain, vertical scratches, dust, a soft vignette; clouds drifting over a horizon.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float frame = floor(t * 24.0);
  vec2 f = c + (vec2(hash(vec2(frame, 1.0)), hash(vec2(frame, 2.0))) - 0.5) * 0.006;
  float lum = 0.55 + 0.25 * smoothstep(-0.3, 0.4, f.y) + 0.2 * (fbm(vec2(f.x * 3.0 - t * 0.04, f.y * 6.0)) - 0.5);
  lum = mix(lum, 0.3 + 0.1 * fbm(vec2(f.x * 10.0 + t * 0.1, f.y * 30.0)), step(f.y, -0.18));
  lum *= 0.85 + 0.15 * hash(vec2(frame, 3.0));
  lum += step(0.995, hash(vec2(floor(f.x * 160.0), floor(frame / 4.0)))) * 0.25;
  lum -= step(0.7, noise(f * 50.0 + frame * 3.1)) * step(0.97, hash(vec2(frame, 4.0))) * 0.5;
  lum += (hash(gl_FragCoord.xy + frame) - 0.5) * 0.12;
  lum *= 1.0 - 0.55 * smoothstep(0.25, 0.65, length(c * vec2(1.2, 0.9)));
  o = vec4(vec3(1.0, 0.86, 0.64) * clamp(lum, 0.0, 1.2), 1.0);
