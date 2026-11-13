import { Request, Response } from "express";
import { db } from "./db";

export async function getDocument(req: Request, res: Response) {
  const doc = await db.documents.findById(req.params.id);
  if (!doc) {
    return res.status(404).json({ error: "Not found" });
  }
  if (doc.ownerId !== req.user.id) {
    return res.status(403).json({ error: "Forbidden" });
  }
  return res.json(doc);
}

export async function deleteDocument(req: Request, res: Response) {
  const doc = await db.documents.findById(req.params.id);
  if (!doc) {
    return res.status(404).json({ error: "Not found" });
  }
  await db.documents.delete(doc.id);
  return res.status(204).send();
}
