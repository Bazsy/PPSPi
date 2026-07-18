## Summary

Describe the problem and the smallest coherent solution.

## Timing and security impact

- Timing-source/source-selection changes:
- Boot, service-ordering, or fallback changes:
- Network exposure or privilege changes:
- Hardware assumptions and authoritative evidence:

## Reproduction and validation

List exact commands and results. Include fixture scenarios or hardware revision,
duration, conditions, and measured offsets where applicable.

## Checklist

- [ ] `make test` passes.
- [ ] Applicable static checks pass.
- [ ] Installer changes remain idempotent in an alternate root.
- [ ] Generated config and JSON schema changes have tests.
- [ ] Documentation and changelog are updated.
- [ ] No secrets, private identifiers, binary images, or unsanitised logs are included.
- [ ] Hardware mappings cite authoritative sources and are not guessed.
- [ ] Hardware-required validation is linked or explicitly marked blocked.
- [ ] Release behavior is unchanged, or the explicit publication gate is preserved.
