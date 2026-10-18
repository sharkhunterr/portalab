// Horreur — something gets out (u_age: seconds, 3.6 s): the light dying, the dark closing in, the heart
  // beating faster and faster in red, a blade stabbing three times, its wounds bleeding; at 2.4 s it gives way — a red
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
  // the stabs: a blade driven in three times out of the dark, each leaving a wound that bleeds
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float at = 0.75 + fk * 0.5;
    vec2 w = vec2(-0.32 + fk * 0.31 + 0.05 * hash(vec2(fk, 1.0)), 0.1 - fk * 0.07);
    float ang = -0.55 + fk * 0.5;
    vec2 q = c - w;
    vec2 r = vec2(q.x * cos(ang) - q.y * sin(ang), q.x * sin(ang) + q.y * cos(ang));
    float s = age - at;
    // the blade, coming down on it for a tenth of a second
    float strike = step(-0.12, s) * step(s, 0.02) * before;
    vec2 b = r - vec2(0.0, clamp(-s / 0.12, 0.0, 1.0) * 0.35);
    float bw = 0.014 * smoothstep(0.0, 0.06, b.y);
    float blade = step(0.0, b.y) * step(b.y, 0.2) * smoothstep(bw + 0.002, bw, abs(b.x));
    float guard = step(0.2, b.y) * step(b.y, 0.214) * step(abs(b.x), 0.045);
    float grip = step(0.214, b.y) * step(b.y, 0.3) * step(abs(b.x), 0.011);
    o = over(o, mix(vec3(0.4, 0.42, 0.45), vec3(0.92, 0.94, 0.97), smoothstep(-bw, bw, b.x)), blade * strike);
    o = over(o, vec3(0.16, 0.12, 0.1), clamp(guard + grip, 0.0, 1.0) * strike);
    float shown = step(0.0, s) * before;
    o = over(o, vec3(1.0, 0.9, 0.85), exp(-length(q) * 32.0) * smoothstep(0.14, 0.0, s) * shown);
    // the wound: a ragged slit across the blade's path, black inside, raw round it, bruised
    float open = smoothstep(0.0, 0.1, s);
    float rag = 0.0035 * (noise(r * 95.0) - 0.5);
    float e = pow(r.x / 0.034, 2.0) + pow((r.y + rag) / max(0.0075 * open, 0.0004), 2.0);
    float inner = smoothstep(1.0, 0.6, e);
    float lips = smoothstep(4.0, 1.2, e);
    float smear = smoothstep(0.55, 0.85, noise(q * 55.0)) * exp(-length(q * vec2(1.0, 1.5)) * 18.0);
    o = over(o, vec3(0.28, 0.02, 0.06), exp(-length(q * vec2(1.0, 1.6)) * 20.0) * 0.5 * shown);
    o = over(o, vec3(0.38, 0.0, 0.02), clamp(smear * 1.6, 0.0, 1.0) * open * shown);
    o = over(o, mix(vec3(0.7, 0.05, 0.08), vec3(0.45, 0.0, 0.03), smoothstep(2.5, 1.2, e)), lips * shown);
    o = over(o, mix(vec3(0.02, 0.0, 0.0), vec3(0.3, 0.0, 0.02), smoothstep(0.0, 0.8, e)), inner * shown);
    o = over(o, vec3(1.0, 0.6, 0.6), smoothstep(0.0025, 0.0, abs(r.y + 0.006 * open)) * step(abs(r.x), 0.022) * 0.35 * open * shown);
    // the blood welling out and running down
    float flow = smoothstep(0.05, 1.0, s) * 0.2;
    float down = w.y - c.y;
    float dw = 0.004 * (1.0 - 0.6 * smoothstep(0.0, flow, down));
    float rx = c.x - w.x - 0.006 * sin(down * 50.0 + fk) - 0.004;
    float run = smoothstep(dw, dw * 0.4, abs(rx)) * step(0.0, down) * step(down, flow);
    float tipdrop = smoothstep(0.007, 0.003, length(c - vec2(w.x + 0.004 + 0.006 * sin(flow * 50.0 + fk), w.y - flow)));
    o = over(o, vec3(0.42, 0.0, 0.03), clamp(run + tipdrop * step(0.02, flow), 0.0, 1.0) * shown);
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
      // a broken line: its direction jumps at each segment
      float seg = floor(r0 * 14.0);
      float bend = dir + 0.22 * (hash(vec2(fk, seg)) - 0.5);
      crack += smoothstep(0.004, 0.0, abs(sin(a - bend)) * r0) * step(0.06, r0) * step(r0, s * 1.4);
    }
    o = over(o, vec3(0.05, 0.0, 0.0), clamp(crack * 1.6, 0.0, 1.0) * fade);
    o = over(o, vec3(1.0, 0.75, 0.7), clamp(crack, 0.0, 1.0) * 0.45 * fade);
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
