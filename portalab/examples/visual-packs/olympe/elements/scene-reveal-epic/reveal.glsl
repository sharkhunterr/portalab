// An epic card turned: Pegasus's wings unfolding behind it on both sides, feathered, one beat, feathers flying
  // off on a golden wind (u_age, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.1, age);
  float open = smoothstep(0.0, 0.7, age);
  float beat = 0.12 * sin(age * 5.0) * smoothstep(0.6, 1.0, age);
  vec2 w = vec2(abs(c.x) - 0.18, c.y - 0.05);
  float ang = atan(w.y, w.x);
  float r = length(w);
  float span = 0.45 * open;
  float wing = step(0.0, w.x) * step(ang, 1.1 + beat) * step(-0.6 + beat, ang) * step(r, span * (0.6 + 0.4 * cos((ang - 0.25) * 1.6)));
  float plumes = 0.85 + 0.15 * step(0.5, fract(ang * 9.0 + r * 4.0));
  o = over(o, vec3(1.0, 0.99, 0.96) * plumes, wing * 0.92 * fade);
  o = over(o, vec3(1.0, 0.88, 0.5), smoothstep(0.03, 0.0, abs(r - span * (0.6 + 0.4 * cos((ang - 0.25) * 1.6)))) * wing * fade);
  o = over(o, vec3(1.0, 0.9, 0.6), fbm(c * 4.0 - vec2(age * 1.5, 0.0)) * smoothstep(0.6, 0.2, length(c)) * 0.25 * fade);
  for (int k = 0; k < 12; k++) {
    float fk = float(k);
    float s = max(age - 0.6 - fk * 0.05, 0.0);
    vec2 at = vec2(sign(hash(vec2(fk, 1.0)) - 0.5) * (0.4 + s * 0.3), 0.1 + (hash(vec2(fk, 2.0)) - 0.5) * 0.4 + s * 0.1);
    vec2 q = mat2(cos(s * 5.0 + fk), -sin(s * 5.0 + fk), sin(s * 5.0 + fk), cos(s * 5.0 + fk)) * (c - at);
    o = over(o, vec3(1.0, 0.98, 0.94), smoothstep(1.0, 0.8, length(q / vec2(0.01, 0.035))) * step(0.001, s) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
