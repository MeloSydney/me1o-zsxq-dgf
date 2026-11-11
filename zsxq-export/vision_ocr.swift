import Vision
import Foundation
import AppKit

// vision_ocr.swift — macOS Vision OCR 命令行工具
// Usage: vision_ocr <image_path>
// Output: x\ty\ttext  (per line, normalized coordinates origin bottom-left)

let args = CommandLine.arguments
guard args.count > 1 else {
    fputs("Usage: vision_ocr <image_path>\n", stderr)
    exit(1)
}
let imagePath = args[1]

guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    fputs("Failed to load image: \(imagePath)\n", stderr)
    exit(1)
}

let semaphore = DispatchSemaphore(value: 0)

let request = VNRecognizeTextRequest { request, error in
    if let error = error {
        fputs("OCR Error: \(error)\n", stderr)
        semaphore.signal()
        return
    }
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        semaphore.signal()
        return
    }
    for obs in observations {
        if let candidate = obs.topCandidates(1).first {
            let x = obs.boundingBox.origin.x
            let y = obs.boundingBox.origin.y
            print("\(x)\t\(y)\t\(candidate.string)")
        }
    }
    semaphore.signal()
}

request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage)
try? handler.perform([request])
semaphore.wait()
