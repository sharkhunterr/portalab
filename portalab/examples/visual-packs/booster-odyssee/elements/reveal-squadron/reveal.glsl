// An epic card turned: a squadron circling it, trading laser fire, explosions bursting round it
  // (u_age: seconds, 2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.4, 1.7, age) * smoothstep(0.0, 0.2, age);
  o = over(o, vec3(0.6, 0.2, 0.9), smoothstep(0.6, 0.15, length(c)) * 0.3 * fade);
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float ang = age * (1.6 + 0.3 * fk) * (mod(fk, 2.0) < 0.5 ? 1.0 : -1.0) + fk * 1.26;
    vec2 orb = vec2(0.36 + 0.03 * fk, 0.44 - 0.02 * fk);
    vec2 fp = vec2(cos(ang), sin(ang)) * orb;
    vec2 vel = normalize(vec2(-sin(ang) * orb.x, cos(ang) * orb.y) * (mod(fk, 2.0) < 0.5 ? 1.0 : -1.0));
    vec2 rel = c - fp;
    vec2 lr = vec2(dot(rel, vel), dot(rel, vec2(-vel.y, vel.x)));
    float dart = step(-0.03, lr.x) * step(lr.x, 0.0) * step(abs(lr.y), (lr.x + 0.03) * 0.45);
    float wings = step(-0.022, lr.x) * step(lr.x, -0.012) * step(abs(lr.y), 0.016);
    float trail = smoothstep(0.003, 0.0, abs(lr.y)) * step(lr.x, -0.03) * smoothstep(-0.2, -0.03, lr.x);
    o = over(o, vec3(0.8, 0.85, 0.95), clamp(dart + wings, 0.0, 1.0) * fade);
    o = over(o, mix(vec3(0.4, 0.8, 1.0), vec3(1.0, 0.5, 0.3), mod(fk, 2.0)), trail * fade);
    // its shots, flying ahead
    float shot = fract(age * 2.5 + fk * 0.3);
    vec2 sp = fp + vel * shot * 0.4;
    vec2 srel = c - sp;
    float bolt = smoothstep(0.003, 0.0, abs(dot(srel, vec2(-vel.y, vel.x)))) * step(0.0, -dot(srel, vel)) * step(-dot(srel, vel), 0.04);
    o = over(o, mix(vec3(0.3, 1.0, 0.4), vec3(1.0, 0.25, 0.2), mod(fk, 2.0)), bolt * fade);
  }
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float ea = fract(age * 0.9 + fk * 0.25);
    vec2 ep = vec2(cos(fk * 1.7 + 0.5), sin(fk * 1.7 + 0.5)) * vec2(0.35, 0.42);
    float rr = length(c - ep);
    o = over(o, mix(vec3(1.0, 0.95, 0.7), vec3(1.0, 0.4, 0.1), ea * 2.0), smoothstep(0.004 + ea * 0.05, 0.0, rr - ea * 0.02) * smoothstep(0.5, 0.0, ea) * fade);
    o = over(o, vec3(1.0, 0.7, 0.4), smoothstep(0.004, 0.0, abs(rr - ea * 0.08)) * smoothstep(0.6, 0.0, ea) * 0.7 * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
