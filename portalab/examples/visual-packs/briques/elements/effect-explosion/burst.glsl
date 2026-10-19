// Brick burst HD — a celebration (gl_FragCoord, u_res, u_age, 3 s): bricks of the primary colours thrown out
  // from the bubble, spinning, then falling back with gravity; a few sparkles where they turn.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.3, age) * smoothstep(0.0, 0.08, age);
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-length(c) * 8.0) * exp(-age * 5.0) * 0.8);
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    float speed = 0.45 + 0.55 * hash(vec2(fk, 2.0));
    vec2 at = vec2(cos(ang), sin(ang) * 0.8 + 0.6) * speed * age + vec2(0.0, -0.75 * age * age);
    float spin = age * (3.0 + 5.0 * hash(vec2(fk, 3.0))) + fk;
    vec2 q = mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * (c - at);
    float w = 0.02 + 0.02 * step(0.5, hash(vec2(fk, 4.0)));
    float body = step(abs(q.x), w) * step(abs(q.y), 0.011);
    float studs = step(0.011, q.y) * step(q.y, 0.017) * step(abs(q.x), w) * step(abs(fract(q.x / 0.011 + 0.5) - 0.5), 0.3);
    float hh = hash(vec2(fk, 5.0));
    vec3 bc = hh < 0.25 ? vec3(0.84, 0.16, 0.16) : (hh < 0.5 ? vec3(0.97, 0.77, 0.12) : (hh < 0.75 ? vec3(0.12, 0.44, 0.84) : vec3(0.16, 0.62, 0.29)));
    bc *= 0.75 + 0.35 * smoothstep(-0.011, 0.011, q.y);
    o = over(o, bc, clamp(body + studs, 0.0, 1.0) * fade);
    o = over(o, vec3(1.0), exp(-length(c - at) * 200.0) * step(0.85, sin(spin * 2.0)) * fade);
  }
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
