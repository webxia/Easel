/** Pure Hypit 0.2.7 syntax bridge. No runtime, author handler, Provider or Build. */
import { readFileSync, realpathSync } from "node:fs";
import { join, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

const PROFILE = "easel-hypit-source@1";
const MAX_INPUT = 4 * 1024 * 1024, MAX_OUTPUT = 16 * 1024 * 1024;
const PINNED = {
  "node_modules/@esbuild/darwin-arm64/bin/esbuild": "b82c6243eb58d520d0bc55cddcf6993dd0f5572f3ab8dc2ba6d77058be043e62",
  "node_modules/@esbuild/darwin-arm64/package.json": "2716c24eaffc7327a0f910d977a72e266daa0d88f2155390dc31af0e164f4a0e",
  "node_modules/esbuild/lib/main.js": "bce772de103e1cbb118f1b7313916caa81f0e85461b3b6e3531607e7ed75ec85",
  "node_modules/esbuild/package.json": "9ce21c976ffbbb95001f460e9e8af7c6d719f748eb70441e617a14dd0b68a5b8",
  "node_modules/get-tsconfig/dist/index.cjs": "1c040b0a49d0e7dbc555c4e1e8acbdc1f74478011ebeec008dd9e38c83722273",
  "node_modules/get-tsconfig/dist/index.mjs": "2bb1e82fea648d598e1067cc5b643105493a63502458694b486f0c581b506503",
  "node_modules/get-tsconfig/package.json": "4e5880985b33ecaa87f6aef1b6581dec5555d88a0738a7379576e80891873355",
  "node_modules/resolve-pkg-maps/dist/index.cjs": "dc0ffaba25e180745bb1ce1622be094bbc97d07dc275c52413eb546580d9ff49",
  "node_modules/resolve-pkg-maps/dist/index.mjs": "5472eb24afa47c614e7edaccb0ccb4c6259f897d875c27057ee00b7c2cdc3672",
  "node_modules/resolve-pkg-maps/package.json": "e372f809865bc3fc6ad75be76a90b031eece36e9d12d283de9955aca6be8537d",
  "node_modules/tsx/dist/client-BQVF1NaW.mjs": "334ad3dbfaf820eeb08dd2fa40750c8316e6f8a61311bdf99defd3c361fbece4",
  "node_modules/tsx/dist/esm/api/index.mjs": "477bed5ef167ef825ec4cb99ed010ac6d70833d1b4e8b46e23825cc6de543d8e",
  "node_modules/tsx/dist/esm/index.mjs": "9fab711543eb155d50fb147f8984e104db348a73b74daee4e3974bec109aa381",
  "node_modules/tsx/dist/get-pipe-path-BHW2eJdv.mjs": "307483caa22c2406677b4bd513bf602b4de3986f3e23eac7724e99c0d7ddc8d6",
  "node_modules/tsx/dist/index-7AaEi15b.mjs": "47851348bc3bbc11413edd4bf44758b7a85e28419847583231d74a182b044e22",
  "node_modules/tsx/dist/index-gbaejti9.mjs": "76febbe946957c96066d1d59293c4a26fc874c05876394cf4c178e4f4d0b6ba8",
  "node_modules/tsx/dist/lexer-DQCqS3nf.mjs": "6b77bebaee2dd7741177e287a78ef4329d9ef91f6939d09cfcf0029b3859f883",
  "node_modules/tsx/dist/node-features-_8ZFwP_x.mjs": "dbf95f05cce9b129a9a89f33f43b7804ab641aa8b256e7cf64ad9f92b880cecc",
  "node_modules/tsx/dist/register-B7jrtLTO.mjs": "10184ddf4354bab38743d80a5844796f26ffc4589d2820781da90c6a67507aaf",
  "node_modules/tsx/dist/register-CFH5oNdT.mjs": "7c7d2d4f757a1a35610b483e0348aee2eb1140968631f4b2105c4b4ad9ffbf0a",
  "node_modules/tsx/dist/require-DQxpCAr4.mjs": "dc1b6944ffaa8f4d70e5007116b9aeac77c1cdf80a62526763eab34a123fa902",
  "node_modules/tsx/dist/temporary-directory-CwHp0_NW.mjs": "e0771b7d9b216d438ff2ade7494a7a3ac6202c66cb752f2cd99bffb3d78226fe",
  "node_modules/tsx/package.json": "6e764b21991c21595441f82387c1451ccd10a3e7a3f0973cc5e3649a12dea7d2",
  "package.json": "1dfb1c44bf70e2b22e8d93ba2ea5892153d2deb2411233206a4be860c62356ae",
  "packages/markup/package.json": "8f252bf21ab60aa8001b836e669bab4ba5d36cd1c176b515e826ac5a2d56d58b",
  "packages/markup/src/element.ts": "b5b3a407acd6d50a96151d3b2b22e01120d82aa209157dafcf62238d57ee234e",
  "packages/markup/src/error.ts": "8548c95fe3732ebd2d60db4e2744af5039d9dd82bbed17e422ade97453294ebe",
  "packages/markup/src/frontend.ts": "06a235c1443904a2d04ab223000c1d6bf227689b715d8621a8b94b717a8d0178",
  "packages/markup/src/host-facet.ts": "8fe277d4b242df5020623babc348ed67f8005a70ead336d4b7659dce8ff62aad",
  "packages/markup/src/index.ts": "48e159c7d9f8cf256906541a568ca8f70459a000bd897295709b75c08d08b693",
  "packages/markup/src/registry.ts": "f6048261d3f73012db0f3795a288314f4419226542c0af2e6780d4b5a7058988",
  "packages/markup/src/syntax.ts": "486d3d6be06e453311e6a399b374535c6f444831ed901fd2badc8d1623eb6bf6",
  "packages/package-loader-node/package.json": "afc816b1727027274bdca012493fbf470f7294b82bb9dac3596f6e8f6655ab9e",
  "packages/package-loader-node/src/distribution-resolution.ts": "cde18c7956abbe2b1eaa679b4f365072f05b06134fd51127bbe4d1802539b6c1",
  "packages/package-loader-node/src/location.ts": "688060dbff9c52cc3f24d4b2b481cb2c903d253881ad2acd8637536e0f29040c",
  "packages/protocol/package.json": "05def9b24e58b4d051e7a5411a248ba2804ba73de8840085ee3e0077e2070d72",
  "packages/protocol/src/build-id.ts": "0b7b5b3dccab184c83cdeaa1a9a3f793b7c72150a3fcd77e9a4fa96cc831ebc7",
  "packages/protocol/src/canonical.ts": "aa9bd48f2272c097f3a0cb6ec666a4b4c951132611fb3cef03972cfed297c128",
  "packages/protocol/src/error.ts": "4964bda4ac1c42f21993eec5ce9ad9c54e3e9e8bcf7c9d1db52de99264f51e9f",
  "packages/protocol/src/identity.ts": "b23960535f32b9d183bcf1e8fca3a698dd06d644fda143205f13623f9d34ae80",
  "packages/protocol/src/index.ts": "dfb3eb775f2905da7d0937c7bba803041ba2b513c66d8471f2ab320d3bc77e8d",
  "packages/protocol/src/module.ts": "6a547aedf8a6465094d5d57b38c074c2ef175d98fab8a1f6d9afdae6c5982123",
  "packages/protocol/src/value.ts": "9f3527819ac7fbfefd6db2afc73a3365e39980a0c97326d3ec701b8c042ebcd8",
  "packages/run-markup/package.json": "c53e6a84630800fd945838265fb5c0847aa47dcb8dab6fb4a17d3bd7c75f4e1c",
  "packages/run-markup/src/syntax.ts": "f5eab8e0f258f0d4543fdc65358fbb02f4d0a007c25d9cb294e71cc7e7aa27ee",
  "packages/source/package.json": "6d8fb91c362597cb2939b5cb02c29ee89644c7303b62264df10e117dafad30ea",
  "packages/source/src/header.ts": "7c5f11ffbff4477fa5735feeca3fcd2ef146368ce8052131284a2c5e996e5fde",
  "packages/svs/package.json": "f120a6758930a70258b325addcddd1e822a45924593acb40b479e63d9c2a280c",
  "packages/svs/src/parser.ts": "6fb4b39fa66bd6c2a1db3deed1c4d1f22162e312c96077c6cc3558900bd327a5"
};
const MODULES = new Set([
  "media", "media-pipeline", "timeline-author", "spatial", "media-track",
  "audio-track", "film", "render-hyperframes", "typography-track", "text", "fonts-open"
].map(name => "@hypit/" + name + "@1").concat("@easel/audio-mix@1"));
const sha = raw => createHash("sha256").update(raw).digest("hex");
let phase = "bootstrap", current;
function fail(code, message, offset) {
  const error = new Error(message);
  Object.assign(error, {code, offset});
  throw error;
}
function finite(value) {
  if (typeof value === "number" && !Number.isFinite(value)) fail("NATIVE_NON_FINITE_VALUE", "Non-finite native value");
  if (value && typeof value === "object") for (const child of Object.values(value)) finite(child);
}
try {
  const raw = readFileSync(0);
  if (raw.length > MAX_INPUT) fail("BRIDGE_INPUT_LIMIT", "Parser input exceeds the fixed capacity");
  const input = JSON.parse(raw.toString("utf8"));
  if (input.profile !== PROFILE || !Array.isArray(input.sources) || !input.sources.length || input.sources.length > 32)
    fail("BRIDGE_INPUT", "Invalid parser invocation");
  const root = realpathSync.native(input.distribution_root);
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  if (pkg.name !== "@hypit/hypit" || pkg.version !== "0.2.7") fail("PARSER_IDENTITY", "Unverified Hypit distribution");
  for (const [path, hash] of Object.entries(PINNED))
    if (sha(readFileSync(join(root, path))) !== hash) fail("PARSER_IDENTITY", "Installed native parser source changed");
  if (process.env.TSX_DISABLE_CACHE !== "1") fail("LOADER_POLICY", "Native parser requires disabled disk transform cache");
  const base = pathToFileURL(root + sep);
  const {register} = await import(pathToFileURL(join(root, "node_modules/tsx/dist/esm/api/index.mjs")).href);
  register({tsconfig:false});
  const {installDistributionPackageResolution} = await import(new URL("packages/package-loader-node/src/distribution-resolution.ts", base));
  installDistributionPackageResolution([root]);
  const [headerApi, markup, svs, run] = await Promise.all([
    import(new URL("packages/source/src/header.ts", base)),
    import(new URL("packages/markup/src/syntax.ts", base)),
    import(new URL("packages/svs/src/parser.ts", base)),
    import(new URL("packages/run-markup/src/syntax.ts", base))
  ]);
  const output = [];
  const names = new Set();
  for (const item of input.sources) {
    phase = "source"; current = item;
    if (typeof item.name !== "string" || !item.name || names.has(item.name) ||
        typeof item.text !== "string" || Buffer.byteLength(item.text) > 512 * 1024 ||
        sha(Buffer.from(item.text, "utf8")) !== item.sha256 || item.text.includes("\0"))
      fail("SOURCE_INPUT", "Invalid bounded source snapshot");
    names.add(item.name);
    const header = headerApi.parseSourceHeader(item.name, item.text);
    const dialect = {markup:"@hypit/markup@1", svs:"@hypit/svs@1", run:"@hypit/run-markup@1"}[item.kind];
    if (!dialect || header.using !== dialect) fail("EASEL_DIALECT_UNSUPPORTED", "Source dialect is outside this fixed profile", header.start);
    const masked = headerApi.maskSourceHeader(item.text, header);
    if (masked.length !== item.text.length) fail("SOURCE_MASK_IDENTITY", "Header masking changed source coordinates");
    const source = {name:item.name, text:masked};
    let ast, discovery;
    if (item.kind === "svs") {
      // This verified release mixes code-point and UTF-16 indexing when removing
      // block comments. Reject that unverified combination; never patch source.
      if (/[\u{10000}-\u{10FFFF}]/u.test(item.text) && item.text.includes("/*"))
        fail("EASEL_SVS_COMMENTS_UNSUPPORTED", "Non-BMP text with SVS block comments is outside this verified profile");
      ast = svs.parseSvs(item.name, masked);
    } else {
      if (item.kind === "markup") {
        discovery = markup.discoverMarkup(source);
        const aliases = new Set();
        for (const imp of discovery.imports) {
          if (imp.alias !== undefined) {
            if (aliases.has(imp.alias)) fail("EASEL_ALIAS_COLLISION", "Import aliases must be unique", imp.range.start);
            aliases.add(imp.alias);
          }
          if (imp.kind === "module" && !MODULES.has(imp.from))
            fail("EASEL_MODULE_UNSUPPORTED", "Module is outside the verified structured production profile", imp.range.start);
          if (imp.kind === "source" && (!/^(?:\.\/)?[^/\\]+\.svs$/.test(imp.from) ||
              imp.from.includes("..") || !imp.alias))
            fail("EASEL_SOURCE_IMPORT_UNSUPPORTED", "Only captured same-directory named SVS imports are supported", imp.range.start);
        }
      }
      const parsed = markup.parseStructuredElement(source, markup.skipTextTrivia(source, 0));
      if (markup.skipTextTrivia(source, parsed.nextOffset) !== masked.length)
        fail("EASEL_TRAILING_SOURCE", "Unexpected content after the complete source", parsed.nextOffset);
      let count = 0;
      function locations(node, depth = 0) {
        if (++count > 10000 || depth > 64) fail("EASEL_AST_LIMIT", "Native source exceeds the fixed AST capacity", node.range.start);
        if (node.kind === "text") return node;
        const opening = markup.parseOpeningTag(source, node.range.start);
        return {...node, openingRange:{start:opening.start,end:opening.end},
          selfClosing:opening.selfClosing, children:node.children.map(child => locations(child, depth+1))};
      }
      ast = locations(parsed.element);
      if (item.kind === "run") {
        const document = run.parseRunDocument(item.name, masked);
        if (document.imports.length || document.candidates.length || document.satisfactions.length)
          fail("EASEL_RUN_UNSUPPORTED", "Only the program-bound author and output target Run is supported");
        ast = {document, element:ast};
      }
    }
    finite(ast);
    output.push({name:item.name, sha256:item.sha256, kind:item.kind, header, ast,
                 ...(discovery ? {discovery} : {})});
  }
  const result = JSON.stringify({schema:PROFILE, ok:true, parser:{
    version:pkg.version,node_version:process.version,node_sha256:sha(readFileSync(process.execPath)),
    loader_policy:{tsconfig:false,disk_cache:false},source_sha256:PINNED}, sources:output});
  if (Buffer.byteLength(result) > MAX_OUTPUT) fail("BRIDGE_OUTPUT_LIMIT", "Native parser output exceeds its fixed capacity");
  process.stdout.write(result);
} catch (error) {
  const diagnostic = {kind:phase, code:typeof error.code === "string" ? error.code : "NATIVE_PARSER_ERROR",
    message:String(error.message || "Native parser failed").slice(0,600),
    source:current?.name, offset_unit:"utf16-code-unit"};
  for (const key of ["offset","line","column"])
    if (Number.isInteger(error[key]) && error[key] >= 0) diagnostic[key] = error[key];
  process.stdout.write(JSON.stringify({schema:PROFILE,ok:false,error:diagnostic}));
  process.exitCode = 1;
}
