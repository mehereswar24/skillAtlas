"use client";

import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
} from "@/components/ui/carousel";
import type { CarouselApi } from "@/components/ui/carousel";
import Link from "next/link";

interface GalleryHoverCarouselItem {
  id: string;
  title: string;
  summary: string;
  url: string;
}

export default function GalleryHoverCarousel({
  heading = "Featured Routes",
  demoUrl = "#",
  items = [],
}: {
  heading?: string;
  demoUrl?: string;
  items?: GalleryHoverCarouselItem[];
}) {
  const [carouselApi, setCarouselApi] = useState<CarouselApi>();
  const [canScrollPrev, setCanScrollPrev] = useState(false);
  const [canScrollNext, setCanScrollNext] = useState(false);

  // Carousel scroll tracking
  useEffect(() => {
    if (!carouselApi) return;
    const update = () => {
      setCanScrollPrev(carouselApi.canScrollPrev());
      setCanScrollNext(carouselApi.canScrollNext());
    };
    update();
    carouselApi.on("select", update);
    return () => {
      carouselApi.off("select", update);
    };
  }, [carouselApi]);

  return (
    <section className="relative">
      <div className="w-full px-8 py-10 md:py-16 md:px-16 lg:px-24">
        <div className="mb-8 flex flex-col justify-between md:mb-14 md:flex-row md:items-end lg:mb-16">
          <div className="max-w-2xl">
            <h3 className="text-lg sm:text-xl lg:text-3xl font-medium leading-relaxed">
            {heading}{" "}
            <span className="text-muted-foreground text-sm sm:text-base lg:text-3xl"> Explore our collection of specialized career paths designed to take you from beginner to expert.</span>
          </h3>
          </div>
          <div className="flex gap-6 mt-4 md:mt-0">
            <Button
              variant="outline"
              size="icon"
              onClick={() => carouselApi?.scrollPrev()}
              disabled={!canScrollPrev}
              className="h-12 w-12 rounded-full hover:scale-105 transition-transform"
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => carouselApi?.scrollNext()}
              disabled={!canScrollNext}
              className="h-12 w-12 rounded-full hover:scale-105 transition-transform"
            >
              <ChevronRight className="h-5 w-5" />
            </Button>
          </div>
        </div>

        <div className="w-full max-w-full">
          <Carousel
            setApi={setCarouselApi}
            opts={{ breakpoints: { "(max-width: 768px)": { dragFree: true } } }}
            className="relative w-full max-w-full"
            autoScroll={true}
            autoScrollInterval={3000}
          >
            <CarouselContent className="hide-scrollbar w-full max-w-full md:ml-4 md:-mr-4">
              {items.map((item) => (
                <CarouselItem key={item.id} className="ml-6 md:max-w-[350px]">
                  <Link href={item.url} className="group block relative w-full h-[300px] md:h-[400px]">
                    <Card className="overflow-hidden rounded-xl h-full w-full rounded-3xl">
                      {/* Image replacement (no images, just a sleek background) */}
                      <div className="relative h-full w-full transition-all duration-500 group-hover:h-1/2 bg-muted overflow-hidden bg-gradient-to-br from-muted to-background border-b border-border/10">
                        {/* Sci-Fi Scanner Sweep Effect */}
                        <div className="absolute inset-0 overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10 pointer-events-none">
                           <div className="w-full h-full bg-gradient-to-b from-transparent via-primary/30 to-transparent -translate-y-full group-hover:translate-y-full transition-transform duration-[1.5s] ease-in-out" />
                        </div>
                        
                        {/* Corner Accents */}
                        <div className="absolute top-4 left-4 w-4 h-4 border-t-2 border-l-2 border-primary opacity-0 group-hover:opacity-100 transition-all duration-500 -translate-x-2 -translate-y-2 group-hover:translate-x-0 group-hover:translate-y-0 z-20 pointer-events-none" />
                        <div className="absolute top-4 right-4 w-4 h-4 border-t-2 border-r-2 border-primary opacity-0 group-hover:opacity-100 transition-all duration-500 translate-x-2 -translate-y-2 group-hover:translate-x-0 group-hover:translate-y-0 z-20 pointer-events-none" />

                        {/* Fade overlay at bottom */}
                        <div className="absolute bottom-0 left-0 w-full h-20 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-10" />
                      </div>

                      {/* Default State Content */}
                      <div className="absolute top-0 left-0 w-full h-full p-6 md:p-8 flex flex-col justify-start z-10 transition-transform duration-500 group-hover:-translate-y-4">
                        <h3 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight text-foreground/70 group-hover:text-foreground transition-colors duration-300">
                          {item.title}
                        </h3>
                      </div>

                      {/* Hover Reveal Section (Summary) */}
                      <div className="absolute bottom-0 left-0 w-full h-[45%] px-6 md:px-8 transition-transform duration-500 translate-y-full group-hover:translate-y-0 flex flex-col justify-center bg-background/95 backdrop-blur-md border-t border-border z-20">
                        <p className="text-muted-foreground text-sm md:text-base leading-relaxed line-clamp-3">
                          {item.summary}
                        </p>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="absolute bottom-4 right-4 hover:bg-transparent transition-all duration-500 rounded-full flex items-center justify-center text-primary group-hover:translate-x-1"
                        >
                          <ArrowRight className="size-5" />
                        </Button>
                      </div>
                    </Card>
                  </Link>
                </CarouselItem>
              ))}
            </CarouselContent>
          </Carousel>
        </div>
      </div>
    </section>
  );
}
