/**
 * #68: the premium ambiences drawn by the GPU — original fragment shaders built from the classic tools
 * (value noise, fractal Brownian motion, domain warping). Each writes premultiplied colour over a
 * transparent page: what is not lit stays see-through. Kept to GLSL ES 1.0 so every phone runs them.
 */

export const COMMON = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2 u_res;
uniform float u_time;
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8); // each octave turned: no grid lines
  for (int i = 0; i < 6; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
// lays a layer of colour c with coverage al over what is already drawn (premultiplied)
vec4 over(vec4 under, vec3 c, float al) {
  al = clamp(al, 0.0, 1.0);
  return vec4(c * al + under.rgb * (1.0 - al), al + under.a * (1.0 - al));
}
float fwidthApprox(float z) {
  return clamp(z * 0.004, 0.0, 0.2);
}
vec2 coords(out vec2 uv) {
  uv = gl_FragCoord.xy / u_res;
  return vec2(uv.x * u_res.x / u_res.y, uv.y);
}
`;
