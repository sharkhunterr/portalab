// An epic card turned: shadows of hands crawling from the edges toward it, fingers stretching, then
  // drawing back into the dark (u_age: seconds, 2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float reach = sin(clamp(age / 2.4, 0.0, 1.0) * 3.1416);
  o = over(o, vec3(0.25, 0.0, 0.02), smoothstep(0.2, 0.9, length(c)) * 0.5 * reach);
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float ang = fk * 1.047 + 0.3;
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 q = c - dir * (0.75 - 0.33 * reach);
    vec2 r = vec2(dot(q, vec2(-dir.y, dir.x)), dot(q, -dir));
    float palm = smoothstep(0.05, 0.035, length(r * vec2(1.0, 1.3)));
    float fingers = 0.0;
    for (int j = 0; j < 4; j++) {
      float fj = float(j);
      float x = (fj - 1.5) * 0.022;
      float len = 0.05 + 0.03 * reach + 0.01 * sin(fj * 2.0 + fk);
      fingers += smoothstep(0.007, 0.004, abs(r.x - x - r.y * 0.15 * (fj - 1.5))) * step(0.0, r.y) * step(r.y, len);
    }
    float arm = smoothstep(0.03, 0.02, abs(r.x)) * step(r.y, 0.0);
    o = over(o, vec3(0.0), clamp(palm + fingers + arm, 0.0, 1.0) * 0.9 * reach);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
