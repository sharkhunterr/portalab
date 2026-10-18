// An epic card turned: livid hands, lit red from behind it, crawling from the edges toward it, fingers
  // stretching, then drawing back into the dark (u_age: seconds, 2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float reach = sin(clamp(age / 2.4, 0.0, 1.0) * 3.1416);
  float thump = exp(-pow((age - 0.15) * 9.0, 2.0)) + 0.7 * exp(-pow((age - 0.42) * 9.0, 2.0));
  o = over(o, vec3(0.5, 0.0, 0.04), smoothstep(0.6, 0.1, length(c)) * (0.55 * reach + 0.35 * thump));
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float ang = fk * 1.047 + 0.3;
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 q = c - dir * (0.46 - 0.16 * reach);
    vec2 r = vec2(dot(q, vec2(-dir.y, dir.x)), dot(q, -dir)) * 0.62;
    float palm = smoothstep(0.05, 0.035, length(r * vec2(1.0, 1.3)));
    float fingers = 0.0;
    for (int j = 0; j < 4; j++) {
      float fj = float(j);
      float x = (fj - 1.5) * 0.022;
      float len = 0.05 + 0.03 * reach + 0.01 * sin(fj * 2.0 + fk);
      fingers += smoothstep(0.007, 0.004, abs(r.x - x - r.y * 0.15 * (fj - 1.5))) * step(0.0, r.y) * step(r.y, len);
    }
    float arm = smoothstep(0.03, 0.02, abs(r.x)) * step(r.y, 0.0);
    float hand = clamp(palm + fingers + arm, 0.0, 1.0);
    // pale, bloodless skin, its edge lit red by the glow behind the card
    o = over(o, vec3(0.62, 0.0, 0.03), smoothstep(0.0, 1.0, hand) * 0.35 * reach);
    o = over(o, mix(vec3(0.32, 0.29, 0.28), vec3(0.6, 0.55, 0.52), smoothstep(-0.05, 0.08, r.y)), hand * 0.92 * reach);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
