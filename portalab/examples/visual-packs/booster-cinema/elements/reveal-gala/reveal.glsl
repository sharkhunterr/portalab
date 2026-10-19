// A legendary card turned: the gala night — the red carpet glowing beneath, two golden searchlights crossing
  // behind, photographers' flashes crackling all round (each a burst with its star), golden stars falling
  // (u_age, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.15, age);
  o = over(o, vec3(0.75, 0.05, 0.08), smoothstep(-0.2, -0.5, c.y) * smoothstep(0.5, 0.1, abs(c.x) - (-c.y - 0.2) * 0.5) * 0.55 * fade);
  for (int k = 0; k < 2; k++) {
    float sd = k == 0 ? -1.0 : 1.0;
    vec2 src = vec2(sd * 0.5, -0.55);
    float ang = 1.5708 - sd * (0.4 + 0.3 * sin(age * 1.6 + float(k)));
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 q = c - src;
    float along = dot(q, dir);
    float beam = smoothstep(0.03 + along * 0.1, 0.0, abs(dot(q, vec2(-dir.y, dir.x)))) * step(0.0, along);
    o = over(o, vec3(1.0, 0.85, 0.45), beam * 0.35 * fade);
  }
  o = over(o, vec3(1.0, 0.9, 0.6), exp(-length(c) * 6.0) * 0.5 * fade);
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float when = hash(vec2(fk, 1.0)) * 2.4;
    float s = age - when;
    float on = step(0.0, s) * exp(-max(s, 0.0) * 14.0);
    float side = hash(vec2(fk, 2.0)) < 0.5 ? -1.0 : 1.0;
    vec2 at = vec2(side * (0.38 + 0.25 * hash(vec2(fk, 3.0))), (hash(vec2(fk, 4.0)) - 0.5) * 0.8);
    vec2 q = c - at;
    float flash = exp(-length(q) * 40.0) + (smoothstep(0.004, 0.0, abs(q.x)) + smoothstep(0.004, 0.0, abs(q.y))) * exp(-length(q) * 12.0) * 0.6;
    o = over(o, vec3(1.0, 1.0, 0.97), clamp(flash, 0.0, 1.0) * on * fade);
  }
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float fall = fract(age * (0.25 + 0.15 * hash(vec2(fk, 5.0))) + hash(vec2(fk, 6.0)));
    vec2 at = vec2((hash(vec2(fk, 7.0)) - 0.5) * 1.1, 0.55 - fall * 1.1);
    vec2 q = c - at;
    float ang = atan(q.y, q.x) + age * 2.0 + fk;
    float star = smoothstep(0.012 * (0.55 + 0.45 * cos(ang * 5.0)), 0.0, length(q) - 0.002);
    o = over(o, vec3(1.0, 0.85, 0.35), star * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
