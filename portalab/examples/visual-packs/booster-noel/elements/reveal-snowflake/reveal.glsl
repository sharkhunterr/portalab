// A rare card turned: a great snowflake drawing itself behind it, turning, then bursting into powder
  // (u_age: seconds, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.3, age) * smoothstep(0.0, 0.1, age);
  float spin = age * 0.8;
  vec2 q = vec2(c.x * cos(spin) - c.y * sin(spin), c.x * sin(spin) + c.y * cos(spin));
  float r = length(q);
  float a = atan(q.y, q.x);
  float arm = mod(a + 0.5236, 1.0472) - 0.5236;
  vec2 ap = vec2(cos(arm), sin(arm)) * r;
  float grow = smoothstep(0.0, 0.7, age) * 0.42;
  float line = smoothstep(0.006, 0.0, abs(ap.y)) * step(ap.x, grow);
  float twig = smoothstep(0.005, 0.0, abs(abs(ap.y) - (ap.x - 0.2) * 0.6)) * step(0.2, ap.x) * step(ap.x, min(grow, 0.32));
  float burst = smoothstep(1.0, 1.6, age);
  o = over(o, vec3(0.85, 0.95, 1.0), (line + twig) * (1.0 - burst) * fade);
  vec2 g = c * 30.0;
  float powder = step(0.8, hash(floor(g))) * smoothstep(0.2, 0.0, length(fract(g) - 0.5)) * smoothstep(0.1 + burst * 0.5, 0.0, length(c) - burst * 0.2);
  o = over(o, vec3(1.0), powder * burst * fade);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
