// CloudFront Function (cloudfront-js-2.0) on viewer request of the default behavior.
// The static export (next.config.ts trailingSlash: true) holds /<route>/index.html, and
// an S3 origin behind origin access control does not map a folder to its index file.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var name = uri.slice(uri.lastIndexOf("/") + 1);
  if (name === "") {
    request.uri = uri + "index.html";
  } else if (name.indexOf(".") === -1) {
    request.uri = uri + "/index.html";
  } else if (name.indexOf("__next.") === 0 && name.slice(-4) === ".txt") {
    // ponytail: a segment prefetch asks for __next.<a>.<b>.txt while the export holds
    // __next.<a>/<b>.txt (TODOS.md accepted item 27); inferred from web/out, not from
    // Next.js docs. A wrong guess only keeps the 404 the router already tolerates.
    var parts = name.slice("__next.".length, -4).split(".");
    if (parts.length > 1) {
      var folder = uri.slice(0, uri.length - name.length);
      request.uri = folder + "__next." + parts.join("/") + ".txt";
    }
  }
  return request;
}
