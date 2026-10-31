// LaserDisc — the booster stage: Memphis, a pastel grid going off to a yellow sun, confetti drifting and turning
  // ringed in black, an iridescent disc spinning in the corner (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(1.0, 0.97, 0.9, 1.0);
  vec2 gq = fract(c * 18.0);
  o = over(o, vec3(0.62, 0.78, 0.95), (step(gq.x, 0.04) + step(gq.y, 0.04)) * 0.6);
  // the sun and its bars
  vec2 su = c - vec2(0.0, 0.05);
  o = over(o, vec3(0.06, 0.06, 0.08), step(length(su - vec2(0.012, -0.012)), 0.2));
  o = over(o, vec3(1.0, 0.84, 0.2), step(length(su), 0.2));
  o = over(o, vec3(0.06, 0.06, 0.08), smoothstep(0.006, 0.0, abs(length(su) - 0.2)));
  // pastel floor: perspective grid
  float hz = -0.12;
  if (c.y < hz) {
    float z = 0.08 / (hz - c.y + 0.001);
    vec2 fl = vec2(c.x * z, z + t * 0.3);
    vec2 ff = abs(fract(fl * vec2(5.0, 3.0)) - 0.5);
    o = over(o, vec3(1.0, 0.6, 0.74), 1.0);
    o = over(o, vec3(0.06, 0.06, 0.08), smoothstep(0.03 + 0.05 * z, 0.0, min(ff.x, ff.y)) * 0.7);
  }
  // confetti: triangles, circles, squiggles
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    vec2 pp = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp, fract(hash(vec2(fk, 2.0)) + t * 0.02 * (0.5 + hash(vec2(fk, 3.0)))) - 0.5);
    vec2 q = c - pp;
    float an = t * 0.6 + fk;
    q = mat2(cos(an), -sin(an), sin(an), cos(an)) * q;
    float kind = mod(fk, 3.0);
    float sd = kind < 1.0 ? sdTri(q, 0.025) : kind < 2.0 ? length(q) - 0.02 : max(abs(q.x) - 0.035, abs(q.y - 0.008 * sin(q.x * 120.0)) - 0.004);
    vec3 col = mod(fk, 5.0) < 1.0 ? vec3(1.0, 0.6, 0.74) : mod(fk, 5.0) < 2.0 ? vec3(0.25, 0.45, 1.0) : mod(fk, 5.0) < 3.0 ? vec3(0.55, 0.9, 0.8) : mod(fk, 5.0) < 4.0 ? vec3(0.62, 0.48, 0.96) : vec3(1.0, 0.42, 0.38);
    o = over(o, vec3(0.06, 0.06, 0.08), step(sd, 0.004));
    o = over(o, col, step(sd, 0.0));
  }
  // the disc, spinning
  vec2 dc = c - vec2(asp * 0.36, 0.3);
  float dr = length(dc), da = atan(dc.y, dc.x);
  vec3 iri = 0.6 + 0.4 * cos(6.2832 * (dr * 6.0 + vec3(0.0, 0.33, 0.67)) + da * 2.0 + t * 2.0);
  o = over(o, vec3(0.06, 0.06, 0.08), step(dr, 0.135));
  o = over(o, iri, step(dr, 0.13) * step(0.02, dr));
