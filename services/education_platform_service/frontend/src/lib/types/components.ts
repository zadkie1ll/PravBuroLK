export interface Course {
    id: number,
    name: string,
    photo_url:string,
    description: string,
    image_url: string,
    modules_count: number,
    completed_modules?: number;
}
export interface Module {
    id: number,
    name: string,
    description: string,
    video_url: string,
    video_is_private?: boolean,
    materials?: ModuleMaterial[],
    order: number,
    status: string
}

export interface ModuleMaterial {
    id: number,
    title: string,
    material_type: string,
    url: string,
    order: number
}
