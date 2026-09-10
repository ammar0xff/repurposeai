# Storage

`StorageProvider` interface: `put / put_file / get / get_path / delete /
exists / list / url`. No raw filesystem calls outside providers.

- `LocalFilesystemStorage`: deterministic layout
  `data/projects/<id>/{source,audio,transcript,candidates,clips,thumbnails,exports,reports}/`.
  Path traversal rejected in `_p()` and `project_key()`.
- `S3Storage`: same key layout under a prefix, presigned URLs for download,
  `get_path()` downloads to a temp file for FFmpeg. Needs `repurposeai[s3]`.

`get_path()` exists because FFmpeg needs real files; remote backends cache
to tempfiles that callers must unlink after use.
