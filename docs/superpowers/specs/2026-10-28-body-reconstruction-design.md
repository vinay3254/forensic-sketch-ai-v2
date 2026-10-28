# Full-body image reconstruction

Approved intent: generated full-body image → local image-to-3D reconstruction → persisted colored GLB → desktop Blender and TRACE viewer. Use existing TripoSR GPU service rather than synthesize more mannequin geometry. A single image gives an approximation, particularly for faces and unseen surfaces.

Retain original image and tie every mesh to its source BodyFigure and case. Offer an explicit build action and keep the mannequin editor separate. Preserve GLB materials/vertex colors. Loading a reconstruction in Blender imports that exact stored mesh through the existing loopback bridge. Missing services and failed inference must produce visible errors and must not replace existing results.

Verified refinement: front-facing geometry receives a projection of the actual source image to preserve visible appearance; other surfaces retain inferred colors. This is disclosed in the UI. Body geometry sampling is 128³ after live 192³ extraction exceeded laptop system RAM. Mannequin previews hide imported reconstructions instead of deleting them. GLB validation checks embedded POSITION geometry before publication.

Alternatives: manual Blender assets cannot reconstruct arbitrary reference appearances; paid reconstruction services conflict with the user's free local preference. Existing cached TripoSR is the first local engine, with quality checked on the actual stored reference.
