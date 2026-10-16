// Portalab — ambient/forest: the « forest » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  float wind = sin(t * 0.5) * 0.6 + sin(t * 1.3) * 0.25;
  vec4 o = vec4(0.0);
  // the canopy's shade: patches of foliage stirring in the wind
  vec2 l = p * 13.0 + vec2(sin(t * 0.3) * 0.4, cos(t * 0.23) * 0.3);
  vec2 sway = vec2(noise(l * 0.3 + t * 0.2), noise(l * 0.3 + vec2(4.0, t * 0.17))) * 1.2;
  float leaves = noise(l * 1.7 + sway) * 0.7 + noise(l * 3.4 + sway * 2.0) * 0.3;
  float canopy = smoothstep(0.35, 0.7, fbm(p * 1.6 + vec2(t * 0.02, 0.0)));
  float dapple = smoothstep(0.58, 0.72, leaves) * canopy * smoothstep(0.2, 1.0, uv.y);
  o = over(o, vec3(0.06, 0.16, 0.05), canopy * 0.3);
  o = over(o, vec3(0.75, 0.92, 0.45), dapple * 0.45);
  // sunbeams slanting from the top left, dust glittering in them
  float bx = p.x + uv.y * 0.6;
  float shafts = smoothstep(0.55, 1.0, sin(bx * 4.0 + sin(bx * 1.7) * 1.5))
    + 0.6 * smoothstep(0.85, 1.0, sin(bx * 11.0 + 1.3));
  float beams = shafts * (0.6 + 0.4 * sin(t * 0.4 + bx * 3.0)) * (0.7 + 0.3 * noise(vec2(bx * 3.0, t * 0.3)));
  beams *= smoothstep(0.0, 0.9, uv.y);
  vec2 mg = p * 90.0 + vec2(sin(t * 0.5) * 2.0, t * 1.5);
  float motes = step(0.988, hash(floor(mg))) * smoothstep(0.35, 0.0, length(fract(mg) - 0.5)) * beams;
  o = over(o, vec3(1.0, 0.93, 0.65), beams * 0.32);
  o = over(o, vec3(1.0, 1.0, 0.85), motes);
  // the canopy's edge at the top: leaves in silhouette, swaying
  float edgeY = 0.9 + 0.05 * fbm(vec2(p.x * 3.0 + wind * 0.1, 1.0)) + 0.03 * noise(vec2(p.x * 14.0 + wind * 0.5, t * 0.3));
  float leafEdge = smoothstep(edgeY, edgeY + 0.01, uv.y + noise(vec2(p.x * 40.0, uv.y * 40.0)) * 0.04);
  o = over(o, vec3(0.02, 0.05, 0.02), leafEdge * 0.85);
  // falling leaves, tumbling
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    float life = 9.0 + hash(vec2(fi, 1.0)) * 6.0;
    float k = floor((t + fi * 2.3) / life);
    float ph = fract((t + fi * 2.3) / life);
    vec2 at = vec2(hash(vec2(k, fi)) * aspect + ph * 0.25 + sin(ph * 12.0 + fi) * 0.05, 1.02 - ph * 1.1);
    float spin = t * (1.5 + hash(vec2(fi, 4.0))) + fi;
    vec2 d = p - at;
    d = mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * d;
    float flip = 0.35 + 0.65 * abs(sin(spin * 0.7));
    float leaf = smoothstep(1.0, 0.8, length(d / vec2(0.022, 0.011 * flip)));
    leaf += smoothstep(0.0012, 0.0, abs(d.y)) * step(abs(d.x), 0.02) * 0.6; // its rib
    vec3 hue = mix(vec3(0.85, 0.55, 0.15), vec3(0.55, 0.65, 0.2), hash(vec2(k, fi + 5.0)));
    o = over(o, hue, leaf * 0.85);
  }
  // mist low over the ground
  float mist = fbm(vec2(p.x * 1.5 + t * 0.04, uv.y * 4.0 - t * 0.02)) * smoothstep(0.4, 0.0, uv.y);
  o = over(o, vec3(0.7, 0.8, 0.75), mist * 0.45);
  gl_FragColor = o;
}