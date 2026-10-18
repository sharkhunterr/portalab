// Horreur — the eye in the keyhole: red, its slit pupil wandering as if it followed you, blinking at odd
  // times; a red glow breathing round the box (a stage over the booster's place: gl_FragCoord, u_res, t).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float pulse = pow(0.5 + 0.5 * sin(t * 6.8), 6.0);
  o = over(o, vec3(0.5, 0.0, 0.02), exp(-dot(c * vec2(1.3, 1.0), c * vec2(1.3, 1.0)) * 8.0) * (0.2 + 0.2 * pulse));
  vec2 e = c - vec2(0.0, -0.005);
  float lid = 1.0 - step(0.93, noise(vec2(t * 1.7, 4.0)));
  float open = 0.013 * lid;
  float eye = smoothstep(0.002, 0.0, (e.x * e.x) / (0.03 * 0.03) + (e.y * e.y) / max(open * open, 0.00001) - 1.0);
  vec2 look = vec2(0.012 * sin(t * 0.7) + 0.006 * sin(t * 2.9), 0.002 * sin(t * 1.3));
  float iris = smoothstep(0.013, 0.011, length(e - look));
  float pupil = smoothstep(0.0025, 0.0015, abs(e.x - look.x)) * iris;
  o = over(o, vec3(0.95, 0.85, 0.75), eye);
  o = over(o, vec3(0.75, 0.0, 0.0), eye * iris);
  o = over(o, vec3(0.02, 0.0, 0.0), eye * pupil);
  o = over(o, vec3(1.0, 0.1, 0.05), exp(-length(e) * 70.0) * 0.35 * lid);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
