// An epic card turned: a witches' sabbath — a circle of runes kindling and turning round it, violet lightning
  // crackling between its points, bats spiralling out of the dark (u_age: seconds, 2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.4, 1.7, age) * smoothstep(0.0, 0.2, age);
  float r = length(c);
  float a = atan(c.y, c.x);
  float spin = age * 0.9;
  float lit = smoothstep(0.0, 0.6, age);
  o = over(o, vec3(0.45, 0.1, 0.7), smoothstep(0.55, 0.1, r) * 0.45 * fade);
  // the circle: two rings, runes between them, a five-pointed star
  float rings = smoothstep(0.004, 0.0, abs(r - 0.4)) + smoothstep(0.004, 0.0, abs(r - 0.46));
  float rune = step(0.42, r) * step(r, 0.445) * step(0.55, fract((a + spin) / 6.2832 * 24.0)) * step(0.5, hash(vec2(floor((a + spin) / 6.2832 * 24.0), 3.0)));
  float star = 0.0;
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float a1 = spin + fk * 2.5133 + 1.5708;
    float a2 = spin + (fk + 2.0) * 2.5133 + 1.5708;
    vec2 p1 = vec2(cos(a1), sin(a1)) * 0.4;
    vec2 p2 = vec2(cos(a2), sin(a2)) * 0.4;
    vec2 pa = c - p1;
    vec2 ba = p2 - p1;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    star += smoothstep(0.004, 0.0, length(pa - ba * h));
    // violet lightning between the points, flickering
    float zig = (noise(vec2(h * 18.0, floor(age * 14.0) + fk)) - 0.5) * 0.05;
    vec2 n = normalize(vec2(-ba.y, ba.x));
    float arc = smoothstep(0.004, 0.0, length(pa - ba * h - n * zig)) * step(0.5, hash(vec2(floor(age * 14.0), fk)));
    o = over(o, vec3(0.9, 0.7, 1.0), arc * lit * fade);
  }
  o = over(o, vec3(0.8, 0.35, 1.0), clamp(rings + rune + star, 0.0, 1.0) * lit * fade);
  o = over(o, vec3(0.7, 0.3, 1.0), exp(-abs(r - 0.43) * 30.0) * 0.35 * lit * fade);
  // bats spiralling out
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float d = 0.1 + age * (0.18 + 0.12 * hash(vec2(fk, 1.0)));
    float ang = hash(vec2(fk, 2.0)) * 6.2832 + age * 2.5 + d * 3.0;
    vec2 b = vec2(cos(ang), sin(ang) * 0.8) * d;
    vec2 q = (c - b) * (60.0 + 25.0 * hash(vec2(fk, 3.0)));
    float flap = sin(age * 30.0 + fk * 1.9);
    float wing = step(abs(q.x), 2.2) * smoothstep(0.4, 0.0, abs(q.y - abs(q.x) * 0.45 * flap - 0.25 * sin(abs(q.x) * 3.0)));
    o = over(o, vec3(0.03, 0.0, 0.05), clamp(wing + smoothstep(0.5, 0.3, length(q * vec2(1.4, 0.9))), 0.0, 1.0) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
