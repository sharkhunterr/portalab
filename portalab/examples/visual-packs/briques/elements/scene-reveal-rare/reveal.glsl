// A rare card turned: bricks flying in from outside and clicking into a frame round it, each landing with a
  // flash (u_age, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.3, age) * smoothstep(0.0, 0.08, age);
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    float along = fk / 20.0;
    float ang = along * 6.2832 + 1.5708;
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 slot = dir / max(abs(dir.x) / 0.36, abs(dir.y) / 0.5);
    float when = 0.05 + hash(vec2(fk, 1.0)) * 0.6;
    float s = clamp((age - when) / 0.3, 0.0, 1.0);
    vec2 from = slot * 2.4;
    vec2 at = mix(from, slot, 1.0 - pow(1.0 - s, 3.0));
    vec2 q = c - at;
    float horiz = step(abs(dir.y) / 0.5, abs(dir.x) / 0.36);
    q = horiz > 0.5 ? q.yx : q;
    float body = step(abs(q.x), 0.035) * step(abs(q.y), 0.014);
    float studs = step(0.014, q.y) * step(q.y, 0.021) * step(abs(q.x), 0.035) * step(abs(fract(q.x / 0.0175 + 0.5) - 0.5), 0.3);
    float hh = hash(vec2(fk, 2.0));
    vec3 bc = hh < 0.33 ? vec3(0.84, 0.16, 0.16) : (hh < 0.66 ? vec3(0.12, 0.44, 0.84) : vec3(0.97, 0.77, 0.12));
    o = over(o, bc * (0.75 + 0.35 * smoothstep(-0.014, 0.014, q.y)), clamp(body + studs, 0.0, 1.0) * step(0.001, s) * fade);
    o = over(o, vec3(1.0), exp(-length(c - slot) * 50.0) * exp(-max(age - when - 0.3, 0.0) * 14.0) * step(when + 0.3, age) * 0.8 * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
