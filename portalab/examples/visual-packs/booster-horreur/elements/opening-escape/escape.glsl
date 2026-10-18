// Horreur — something gets out (u_age: seconds, 3.6 s): the light dying, the dark closing in, the heart
  // beating faster and faster in red, claw scratches appearing in the dark; at 2.4 s it gives way — a red
  // and white strobe, cracks running out, the eye wide open behind, then the red ebbing away.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float burst = 2.4;
  float before = step(age, burst);
  float dark = smoothstep(0.0, burst, age);
  o = over(o, vec3(0.0), smoothstep(0.08, 0.5, length(c)) * dark * 0.92 * before);
  // the heart: faster and faster
  float rate = 4.0 + age * age * 4.0;
  float beat = pow(0.5 + 0.5 * sin(age * rate), 10.0);
  o = over(o, vec3(0.6, 0.0, 0.02), smoothstep(0.15, 0.7, length(c)) * beat * 0.6 * dark * before);
  // scratches in the dark: three claws, appearing one after the other
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float shown = step(0.9 + fk * 0.45, age) * before;
    vec2 q = c - vec2(-0.35 + fk * 0.35, 0.12 - fk * 0.08);
    vec2 r = vec2(q.x * 0.8 + q.y * 0.6, -q.x * 0.6 + q.y * 0.8);
    float claws = 0.0;
    for (int j = 0; j < 3; j++) {
      float fj = float(j);
      claws += smoothstep(0.004, 0.0, abs(r.x - (fj - 1.0) * 0.025)) * step(abs(r.y), 0.09);
    }
    o = over(o, vec3(0.85, 0.8, 0.75), claws * shown * 0.7);
  }
  if (age > burst) {
    float s = age - burst;
    float fade = smoothstep(1.2, 0.5, s);
    float strobe = step(0.5, fract(s * 14.0)) * smoothstep(0.6, 0.0, s);
    o = over(o, mix(vec3(1.0), vec3(0.9, 0.0, 0.0), step(0.5, fract(s * 7.0))), strobe * 0.8);
    // cracks running out from the middle
    float a = atan(c.y, c.x);
    float r0 = length(c);
    float crack = 0.0;
    for (int k = 0; k < 9; k++) {
      float fk = float(k);
      float dir = fk * 0.698 + hash(vec2(fk, 2.0)) * 0.4;
      float bend = dir + 0.15 * sin(r0 * 25.0 + fk);
      crack += smoothstep(0.012, 0.0, abs(sin(a - bend)) * r0) * step(r0, s * 1.4);
    }
    o = over(o, vec3(1.0, 0.85, 0.8), clamp(crack, 0.0, 1.0) * fade);
    // the eye, wide open, behind it all
    vec2 e = c * vec2(1.0, 2.2);
    float eye = smoothstep(0.31, 0.3, length(e)) * smoothstep(0.0, 0.25, s);
    float iris = smoothstep(0.13, 0.12, length(c));
    float pupil = smoothstep(0.02, 0.012, abs(c.x)) * iris;
    o = over(o, vec3(0.85, 0.78, 0.7), eye * 0.85 * fade);
    o = over(o, vec3(0.7, 0.0, 0.0), eye * iris * fade);
    o = over(o, vec3(0.0), eye * pupil * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
