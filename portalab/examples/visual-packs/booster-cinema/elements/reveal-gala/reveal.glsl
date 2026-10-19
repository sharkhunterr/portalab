// A legendary card turned: the premiere — a white flash and a golden shockwave; a glory of rays turning
  // behind the card; the red carpet running down toward us in perspective, its velvet, its gold posts and
  // their sagging ropes; three searchlights sweeping; the photographers' flashes crackling (each a bloom with
  // its star); golden confetti tumbling down, catching the light as they turn (u_age, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.3, age) * smoothstep(0.0, 0.1, age);
  float r = length(c);
  float a = atan(c.y, c.x);
  o = over(o, vec3(1.0, 0.97, 0.88), exp(-age * 9.0) * exp(-r * 1.5) * 0.8);
  o = over(o, vec3(1.0, 0.82, 0.4), smoothstep(0.03, 0.0, abs(r - age * 1.1)) * smoothstep(0.7, 0.1, age) * 0.9);
  // the glory of rays
  float glory = pow(0.5 + 0.5 * sin(a * 16.0 + age * 0.7), 6.0) * 0.6 + pow(0.5 + 0.5 * sin(a * 7.0 - age * 0.4), 10.0) * 0.5;
  o = over(o, vec3(1.0, 0.85, 0.45), glory * smoothstep(1.0, 0.25, r) * smoothstep(0.1, 0.3, age) * fade * 0.6);
  o = over(o, vec3(1.0, 0.92, 0.7), exp(-r * 5.0) * 0.55 * fade);
  // the red carpet in perspective, and its gold posts and ropes
  float h = 0.08;
  float yc = c.y + 0.12;
  float z = h / max(-yc, 0.0005);
  float wx = c.x * z;
  float carpet = step(yc, 0.0) * smoothstep(0.205, 0.195, abs(wx)) * smoothstep(0.0, 0.03, -yc);
  vec3 velvet = vec3(0.62, 0.04, 0.08) * (0.7 + 0.3 * fbm(vec2(wx * 30.0, z * 6.0))) * (0.55 + 0.45 * smoothstep(3.0, 0.4, z));
  velvet += vec3(1.0, 0.75, 0.4) * smoothstep(0.012, 0.0, abs(abs(wx) - 0.19)) * 0.6;
  o = over(o, velvet, carpet * smoothstep(0.1, 0.35, age) * fade);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float sd = mod(fk, 2.0) < 0.5 ? -1.0 : 1.0;
    float zp = 0.45 + floor(fk / 2.0) * 0.45;
    vec2 base = vec2(sd * 0.24 / zp, -0.12 - h / zp);
    float ph = 0.07 / zp;
    float post = step(abs(c.x - base.x), 0.006 / zp) * step(base.y, c.y) * step(c.y, base.y + ph);
    float knob = smoothstep(0.011 / zp, 0.008 / zp, length(c - base - vec2(0.0, ph)));
    vec2 next = vec2(sd * 0.24 / (zp + 0.45), -0.12 - h / (zp + 0.45) + 0.07 / (zp + 0.45));
    vec2 top = base + vec2(0.0, ph);
    float u = clamp((c.x - top.x) / (next.x - top.x), 0.0, 1.0);
    float ropeY = mix(top.y, next.y, u) - 0.035 / zp * sin(u * 3.1416);
    float rope = smoothstep(0.004 / zp, 0.0, abs(c.y - ropeY)) * step(min(top.x, next.x), c.x) * step(c.x, max(top.x, next.x)) * step(fk, 5.5);
    o = over(o, vec3(0.95, 0.75, 0.3), clamp(post + knob, 0.0, 1.0) * smoothstep(0.2, 0.4, age) * fade);
    o = over(o, vec3(0.7, 0.05, 0.1), rope * smoothstep(0.2, 0.4, age) * fade);
  }
  // three searchlights sweeping the sky
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 src = vec2((fk - 1.0) * 0.55, -0.6);
    float ang = 1.5708 + 0.5 * sin(age * 1.3 + fk * 2.1);
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 q = c - src;
    float along = dot(q, dir);
    float beam = smoothstep(0.02 + along * 0.09, 0.0, abs(dot(q, vec2(-dir.y, dir.x)))) * step(0.0, along) * smoothstep(1.4, 0.4, along);
    o = over(o, vec3(1.0, 0.92, 0.7), beam * 0.22 * fade);
  }
  // the photographers' flashes
  for (int k = 0; k < 22; k++) {
    float fk = float(k);
    float when = 0.3 + hash(vec2(fk, 1.0)) * 2.3;
    float s = age - when;
    float on = step(0.0, s) * exp(-max(s, 0.0) * 16.0);
    float side = hash(vec2(fk, 2.0)) < 0.5 ? -1.0 : 1.0;
    vec2 at = vec2(side * (0.36 + 0.3 * hash(vec2(fk, 3.0))), -0.05 - 0.4 * hash(vec2(fk, 4.0)));
    vec2 q = c - at;
    float bloom = exp(-length(q) * 30.0);
    float spikes = (smoothstep(0.003, 0.0, abs(q.x)) + smoothstep(0.003, 0.0, abs(q.y)) + 0.6 * smoothstep(0.003, 0.0, abs(q.x - q.y)) + 0.6 * smoothstep(0.003, 0.0, abs(q.x + q.y))) * exp(-length(q) * 9.0);
    o = over(o, vec3(1.0, 1.0, 0.97), clamp(bloom + spikes * 0.8, 0.0, 1.0) * on * fade);
    o = over(o, vec3(1.0, 1.0, 1.0), on * 0.05 * fade);
  }
  // golden confetti tumbling down
  for (int k = 0; k < 40; k++) {
    float fk = float(k);
    float fall = fract(age * (0.22 + 0.12 * hash(vec2(fk, 5.0))) + hash(vec2(fk, 6.0)));
    vec2 at = vec2((hash(vec2(fk, 7.0)) - 0.5) * 1.3 + 0.05 * sin(fall * 10.0 + fk), 0.6 - fall * 1.2);
    float spin = age * (4.0 + 3.0 * hash(vec2(fk, 8.0))) + fk;
    vec2 q = c - at;
    q = mat2(cos(spin * 0.5), -sin(spin * 0.5), sin(spin * 0.5), cos(spin * 0.5)) * q;
    float face = abs(cos(spin));
    float piece = step(abs(q.x), 0.009 * face + 0.001) * step(abs(q.y), 0.005);
    vec3 col = mix(vec3(0.8, 0.55, 0.15), vec3(1.0, 0.95, 0.75), face) * mix(1.0, 1.15, step(0.7, hash(vec2(fk, 9.0))));
    o = over(o, col, piece * smoothstep(0.2, 0.5, age) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
